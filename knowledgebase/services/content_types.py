from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class DocumentType(Enum):
    PDF = 'pdf'
    DOCX = 'docx'
    TXT = 'txt'
    MARKDOWN = 'markdown'
    HTML = 'html'
    PYTHON = 'code/python'
    JSX = 'code/jsx'

@dataclass
class TextSegment:
    """Represents a segment of text with its metadata"""
    text: str
    segment_type: str  # 'paragraph', 'header', 'footer', 'table_cell', 'component', 'function', etc.
    segment_index: int
    char_count: int
    metadata: Dict[str, Any]  # Now includes project context

@dataclass
class DocumentSection:
    """Represents a section in the document"""
    heading: Optional[str]
    segments: List[TextSegment]
    section_index: int
    char_count: int

@dataclass
class DocumentMetadata:
    """Standardized metadata for all document types"""
    total_chars: int
    sections: List[DocumentSection]
    document_type: DocumentType  # Changed from str to DocumentType
    creation_date: Optional[datetime]
    last_modified_date: Optional[datetime]
    author: Optional[str]
    title: Optional[str]
    page_count: Optional[int]
    language: Optional[str]
    extracted_at: datetime = datetime.utcnow()
    # Add project context
    project_name: Optional[str] = None
    project_root: Optional[str] = None
    relative_path: Optional[str] = None
    absolute_path: Optional[str] = None
    git_info: Optional[Dict[str, str]] = None  # branch, commit hash, etc.

@dataclass
class ExtractedContent:
    """Standard return type for all content extraction"""
    text: str
    metadata: DocumentMetadata 

@dataclass
class VectorChunk:
    """Represents a chunk ready for vectorization"""
    text: str
    object_id: str
    user_id: str
    organization_id: str
    agent_id: Optional[str]
    metadata: Dict[str, Any] 