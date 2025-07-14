from typing import Type, get_type_hints, Union, Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
import ast
import importlib.util
import re
import uuid
from enum import Enum
import sys

# Decorator to exclude models from SQL generation
def exclude_from_db(cls):
    """Decorator to mark a model as excluded from database generation"""
    cls._exclude_from_db = True
    return cls

class PydanticToSQL:
    def __init__(self):
        self.models = []
        self.model_classes = {}  # Store model classes for relationship resolution
        self.model_definitions = {}  # Store AST-based model definitions
        self.sql_statements = []
        self.foreign_keys = []  # Store FK constraints to add at the end
        self.skip_folders = {
            '.venv', 'venv', 'env', '.env',
            '__pycache__', '.pytest_cache',
            'node_modules',
            '.git', '.svn', '.hg',
            'migrations',
            'dist', 'build', '*.egg-info',
            '.tox', '.coverage', 'htmlcov',
            '.idea', '.vscode',
        }
        
    def should_skip_path(self, path: Path) -> bool:
        """Check if a path should be skipped"""
        path_parts = set(path.parts)
        return bool(path_parts.intersection(self.skip_folders))
    
    def camel_to_snake(self, name: str) -> str:
        """Convert CamelCase to snake_case"""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def detect_foreign_key_from_name(self, field_name: str, model_name: str) -> Optional[str]:
        """Detect foreign key relationships based on exact naming conventions"""
        if field_name == 'id':
            return None
            
        if field_name.endswith('_id'):
            potential_table = field_name[:-3]
            
            # Check both loaded classes and AST definitions
            all_models = set(self.model_classes.keys()) | set(self.model_definitions.keys())
            
            for stored_model_name in all_models:
                stored_table_name = self.camel_to_snake(stored_model_name)
                
                if stored_table_name == potential_table:
                    return stored_model_name
            
            if potential_table == "user":
                for stored_model_name in all_models:
                    if stored_model_name == "User":
                        return stored_model_name
        
        return None
    
    def parse_field_description_for_fk(self, field_info) -> Optional[tuple]:
        """Parse field description for foreign key information"""
        if field_info and hasattr(field_info, 'description') and field_info.description:
            desc = field_info.description
            if desc.startswith("FK:"):
                parts = desc.split(":")
                if len(parts) >= 2:
                    target_model = parts[1]
                    on_delete = parts[2] if len(parts) > 2 else "CASCADE"
                    return (target_model, on_delete)
        return None
    
    def parse_type_annotation_from_ast(self, annotation_node) -> str:
        """Parse type annotation from AST node to determine SQL type"""
        if annotation_node is None:
            return "TEXT"
        
        # Simple name (str, int, etc.)
        if isinstance(annotation_node, ast.Name):
            type_name = annotation_node.id
            type_mapping = {
                'str': "TEXT",
                'int': "INTEGER",
                'float': "DOUBLE PRECISION",
                'bool': "BOOLEAN",
                'datetime': "TIMESTAMP WITH TIME ZONE",
                'date': "DATE",
                'UUID': "UUID",
                'uuid': "UUID",
                'Decimal': "DECIMAL(10, 2)",
                'list': "JSONB",
                'dict': "JSONB",
            }
            # If it's not a known type, it might be an Enum or custom type
            return type_mapping.get(type_name, "TEXT")
        
        # Optional[type] or Union[type, None]
        elif isinstance(annotation_node, ast.Subscript):
            if isinstance(annotation_node.value, ast.Name):
                if annotation_node.value.id in ['Optional', 'Union']:
                    # For Optional/Union, get the first non-None type
                    if isinstance(annotation_node.slice, ast.Name):
                        return self.parse_type_annotation_from_ast(annotation_node.slice)
                    elif isinstance(annotation_node.slice, ast.Tuple):
                        # Union with multiple types, use first non-None
                        for elt in annotation_node.slice.elts:
                            if not (isinstance(elt, ast.Constant) and elt.value is None):
                                return self.parse_type_annotation_from_ast(elt)
                elif annotation_node.value.id in ['List', 'Dict']:
                    return "JSONB"
        
        # Default to TEXT for unknown types
        return "TEXT"
    
    def extract_model_fields_from_ast(self, class_node: ast.ClassDef) -> Dict[str, Dict]:
        """Extract field information directly from AST"""
        fields = {}
        
        for node in class_node.body:
            # Look for annotated assignments (field: type = value)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                field_name = node.target.id
                sql_type = self.parse_type_annotation_from_ast(node.annotation)
                
                # Check if it's optional (has a default value)
                nullable = node.value is not None
                
                fields[field_name] = {
                    'sql_type': sql_type,
                    'nullable': nullable,
                    'annotation_node': node.annotation
                }
        
        return fields
    
    def generate_create_table_from_ast(self, model_name: str, fields: Dict[str, Dict]) -> str:
        """Generate CREATE TABLE statement from AST-extracted fields"""
        table_name = self.camel_to_snake(model_name)
        columns = []
        
        # Check if model has custom id field
        if 'id' in fields:
            id_type = fields['id']['sql_type']
            if id_type == "TEXT":
                columns.append("id TEXT PRIMARY KEY")
            else:
                columns.append("id UUID PRIMARY KEY DEFAULT gen_random_uuid()")
        else:
            columns.append("id UUID PRIMARY KEY DEFAULT gen_random_uuid()")
        
        for field_name, field_info in fields.items():
            if field_name == 'id':
                continue
            
            # Check for foreign key
            fk_info = None
            if field_name.endswith('_id'):
                detected_model = self.detect_foreign_key_from_name(field_name, model_name)
                if detected_model:
                    fk_info = (detected_model, "CASCADE")
            
            postgres_type = field_info['sql_type']
            
            # If it's a foreign key, check if we need UUID or TEXT
            if fk_info:
                # Default to UUID for foreign keys
                postgres_type = "UUID"
                # But check if the target model uses TEXT ids
                target_model = fk_info[0]
                if target_model in self.model_definitions:
                    target_fields = self.model_definitions[target_model]
                    if 'id' in target_fields and target_fields['id']['sql_type'] == "TEXT":
                        postgres_type = "TEXT"
            
            null_constraint = "" if field_info.get('nullable', False) else " NOT NULL"
            columns.append(f"{field_name} {postgres_type}{null_constraint}")
            
            # Store foreign key constraint
            if fk_info:
                target_model, on_delete = fk_info
                target_table = self.camel_to_snake(target_model)
                self.foreign_keys.append({
                    'table': table_name,
                    'column': field_name,
                    'target_table': target_table,
                    'target_column': 'id',
                    'on_delete': on_delete
                })
        
        # Add timestamps
        columns.append("created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        columns.append("updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        
        create_statement = f"""CREATE TABLE IF NOT EXISTS {table_name} (
    {',\n    '.join(columns)}
);"""
        
        trigger_statement = f"""
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_{table_name}_updated_at BEFORE UPDATE
ON {table_name} FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"""
        
        return create_statement + "\n" + trigger_statement
    
    def generate_create_table(self, model_name: str, model_class: Type[BaseModel]) -> str:
        """Generate CREATE TABLE statement for a successfully loaded Pydantic model"""
        table_name = self.camel_to_snake(model_name)
        columns = ["id UUID PRIMARY KEY DEFAULT gen_random_uuid()"]
        
        model_fields = model_class.model_fields
        
        for field_name, field_info in model_fields.items():
            if field_name == 'id':
                continue
            
            # Try to determine field type
            field_type = str  # Default
            if hasattr(field_info, 'annotation'):
                field_type = field_info.annotation
            
            fk_info = self.parse_field_description_for_fk(field_info)
            
            if not fk_info and field_name.endswith('_id'):
                detected_model = self.detect_foreign_key_from_name(field_name, model_name)
                if detected_model:
                    fk_info = (detected_model, "CASCADE")
            
            postgres_type = self.python_type_to_postgres(field_type, field_name)
            
            nullable = False
            if hasattr(field_info, 'is_required'):
                nullable = not field_info.is_required()
            
            null_constraint = "" if nullable else " NOT NULL"
            
            if fk_info:
                postgres_type = "UUID"
                
            columns.append(f"{field_name} {postgres_type}{null_constraint}")
            
            if fk_info:
                target_model, on_delete = fk_info
                target_table = self.camel_to_snake(target_model)
                self.foreign_keys.append({
                    'table': table_name,
                    'column': field_name,
                    'target_table': target_table,
                    'target_column': 'id',
                    'on_delete': on_delete
                })
        
        columns.append("created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        columns.append("updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        
        create_statement = f"""CREATE TABLE IF NOT EXISTS {table_name} (
    {',\n    '.join(columns)}
);"""
        
        trigger_statement = f"""
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_{table_name}_updated_at BEFORE UPDATE
ON {table_name} FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"""
        
        return create_statement + "\n" + trigger_statement
    
    def python_type_to_postgres(self, python_type: Type, field_name: str = None) -> str:
        """Convert Python type to PostgreSQL type"""
        if isinstance(python_type, type) and issubclass(python_type, Enum):
            return "TEXT"
            
        origin = getattr(python_type, '__origin__', None)
        
        if origin is Union:
            args = python_type.__args__
            if type(None) in args:
                actual_type = next(arg for arg in args if arg is not type(None))
                return self.python_type_to_postgres(actual_type, field_name)
        
        if python_type == uuid.UUID:
            return "UUID"
            
        type_mapping = {
            str: "TEXT",
            int: "INTEGER",
            float: "DOUBLE PRECISION",
            bool: "BOOLEAN",
            datetime: "TIMESTAMP WITH TIME ZONE",
            date: "DATE",
            Decimal: "DECIMAL(10, 2)",
            list: "JSONB",
            dict: "JSONB",
        }
        
        return type_mapping.get(python_type, "TEXT")
    
    def generate_foreign_key_constraints(self) -> str:
        """Generate ALTER TABLE statements for foreign key constraints"""
        if not self.foreign_keys:
            return ""
            
        statements = ["\n-- Foreign Key Constraints"]
        
        for fk in self.foreign_keys:
            constraint_name = f"fk_{fk['table']}_{fk['column']}"
            statement = f"""ALTER TABLE {fk['table']} 
ADD CONSTRAINT {constraint_name} 
FOREIGN KEY ({fk['column']}) 
REFERENCES {fk['target_table']}({fk['target_column']}) 
ON DELETE {fk['on_delete']};"""
            statements.append(statement)
        
        return "\n\n".join(statements)
    
    def find_and_convert_models(self, project_root: Path):
        """Find all Pydantic models and generate SQL"""
        processed_files = 0
        skipped_files = 0
        
        print("First pass: Collecting all models...")
        for py_file in project_root.rglob("*.py"):
            if self.should_skip_path(py_file):
                skipped_files += 1
                continue
            
            if any(skip_dir in str(py_file) for skip_dir in self.skip_folders):
                skipped_files += 1
                continue
            
            try:
                processed_files += 1
                
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                has_pydantic = any(
                    (isinstance(node, ast.ImportFrom) and node.module and 'pydantic' in node.module) or
                    (isinstance(node, ast.Import) and any(alias.name == 'pydantic' for alias in node.names))
                    for node in ast.walk(tree)
                )
                
                if has_pydantic:
                    # First, extract models from AST (always works)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for base in node.bases:
                                if (isinstance(base, ast.Name) and base.id == 'BaseModel') or \
                                   (isinstance(base, ast.Attribute) and base.attr == 'BaseModel'):
                                    # Extract fields from AST
                                    fields = self.extract_model_fields_from_ast(node)
                                    self.model_definitions[node.name] = fields
                                    print(f"  ✓ Found model from AST: {node.name}")
                    
                    # Then try to load the module dynamically (might fail with relative imports)
                    try:
                        file_dir = str(py_file.parent)
                        sys.path.insert(0, file_dir)
                        
                        spec = importlib.util.spec_from_file_location("module", py_file)
                        module = importlib.util.module_from_spec(spec)
                        module.__package__ = ''
                        
                        spec.loader.exec_module(module)
                        
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                for base in node.bases:
                                    if (isinstance(base, ast.Name) and base.id == 'BaseModel') or \
                                       (isinstance(base, ast.Attribute) and base.attr == 'BaseModel'):
                                        try:
                                            model_class = getattr(module, node.name)
                                            if issubclass(model_class, BaseModel):
                                                if hasattr(model_class, '_exclude_from_db') and model_class._exclude_from_db:
                                                    print(f"  - Skipping excluded model: {node.name}")
                                                    # Remove from AST definitions too
                                                    if node.name in self.model_definitions:
                                                        del self.model_definitions[node.name]
                                                    continue
                                                
                                                self.model_classes[node.name] = model_class
                                                print(f"  ✓ Successfully loaded model class: {node.name}")
                                        except Exception as e:
                                            print(f"  ! Could not load class for {node.name}, will use AST definition")
                    except Exception as e:
                        print(f"  ! Could not import module {py_file.name} (likely due to relative imports), using AST definitions")
                    finally:
                        if file_dir in sys.path:
                            sys.path.remove(file_dir)
                                        
            except Exception as e:
                print(f"  ✗ Error processing {py_file}: {e}")
        
        print("\nSecond pass: Generating SQL...")
        
        # Generate SQL for successfully loaded models
        for model_name, model_class in self.model_classes.items():
            try:
                sql = self.generate_create_table(model_name, model_class)
                self.sql_statements.append(sql)
                print(f"  ✓ Generated SQL for {model_name} -> table: {self.camel_to_snake(model_name)}")
            except Exception as e:
                print(f"  ✗ Error generating SQL for {model_name}: {e}")
        
        # Generate SQL for models that couldn't be loaded (using AST)
        for model_name, fields in self.model_definitions.items():
            if model_name not in self.model_classes:  # Only if not already processed
                try:
                    sql = self.generate_create_table_from_ast(model_name, fields)
                    self.sql_statements.append(sql)
                    print(f"  ✓ Generated SQL for {model_name} (from AST) -> table: {self.camel_to_snake(model_name)}")
                except Exception as e:
                    print(f"  ✗ Error generating SQL for {model_name}: {e}")
        
        print(f"\nProcessed {processed_files} files, skipped {skipped_files} files")
        print(f"Found {len(self.model_classes)} fully loaded models and {len(self.model_definitions)} AST-parsed models")
    
    def save_migrations(self, output_path: Path):
        """Save all SQL statements to a file"""
        if not self.sql_statements:
            print("\nNo Pydantic models found to generate SQL!")
            return
        
        uuid_extension = "-- Enable UUID extension\nCREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
        fk_constraints = self.generate_foreign_key_constraints()
        
        migration_sql = """-- Auto-generated PostgreSQL migrations from Pydantic models
-- Generated at: {}

BEGIN;

{}

{}

{}

COMMIT;
""".format(
            datetime.now().isoformat(),
            uuid_extension,
            "\n\n".join(self.sql_statements),
            fk_constraints
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(migration_sql)
        
        print(f"\nGenerated {len(self.sql_statements)} table definitions")
        print(f"Generated {len(self.foreign_keys)} foreign key constraints")
        print(f"Saved to: {output_path}")
        print("\nTo apply migrations:")
        print(f"psql -U your_user -d your_database -f {output_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate SQL migrations from Pydantic models')
    parser.add_argument('--root', type=Path, default=Path.cwd(),
                        help='Project root directory (default: current directory)')
    parser.add_argument('--output', type=Path, default=Path("migrations.sql"),
                        help='Output SQL file path (default: migrations.sql)')
    parser.add_argument('--exclude', nargs='*', 
                        help='Additional folders to exclude')
    
    args = parser.parse_args()
    
    converter = PydanticToSQL()
    
    if args.exclude:
        converter.skip_folders.update(args.exclude)
    
    print(f"Scanning for Pydantic models in: {args.root}")
    print(f"Excluding folders: {', '.join(sorted(converter.skip_folders))}\n")
    
    converter.find_and_convert_models(args.root)
    converter.save_migrations(args.output)