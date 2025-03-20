from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    MarkdownTextSplitter,
    PythonCodeTextSplitter,
    # HTMLTextSplitter,
    TextSplitter
)
from .content_types import (
    ExtractedContent, 
    TextSegment, 
    DocumentSection, 
    DocumentType,
    VectorChunk
)
from .metadata_service import MetadataService
from .chunk_report_service import ChunkReportService
from llm.services.llm_service import LLMService
from llm.services.llm_provider import LLMProvider
from common.logger.logger_service import get_logger

logger = get_logger()

# Define valid splitter types
SplitterType = Literal[
    "recursive", 
    "character", 
    "markdown", 
    "code",
    "html"
]

@dataclass
class ChunkingConfig:
    """Configuration for text chunking"""
    chunk_size: int = 500
    chunk_overlap: int = 50
    splitter_type: SplitterType = "recursive"
    separators: Optional[List[str]] = None
    
    def get_splitter(self) -> TextSplitter:
        """Creates a text splitter based on configuration"""
        base_args = {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "length_function": len,
            "separators": self.separators if self.separators else ["\n\n", "\n", " ", ""]
        }
            
        splitters = {
            "recursive": lambda: RecursiveCharacterTextSplitter(**base_args),
            "character": lambda: CharacterTextSplitter(**base_args),
            "markdown": lambda: MarkdownTextSplitter(**base_args),
            "code": lambda: PythonCodeTextSplitter(**base_args),
            # "html": lambda: HTMLTextSplitter(**base_args),
        }
        
        return splitters[self.splitter_type]()

class ChunkingService:
    def __init__(self):
        self.metadata_service = MetadataService()
        self.default_config = ChunkingConfig()
        self.report_service = ChunkReportService()
    
    async def create_chunks(
        self,
        extracted_content: ExtractedContent,
        object_metadata: Dict[str, Any],
        object_id: str,
        user_id: str,
        config: Optional[ChunkingConfig] = None,
        generate_report: bool = False,
        report_path: Optional[str] = None
    ) -> List[VectorChunk]:
        """
        Creates optimized chunks from extracted content while preserving metadata
        
        Args:
            extracted_content: The extracted content with its metadata
            object_metadata: Business metadata from the domain object model
            object_id: ID of the source object (e.g., reference_id)
            user_id: ID of the user who owns this content
            organization_id: ID of the organization
            agent_id: Optional ID of the agent if content is agent-specific
            config: Optional chunking configuration. If not provided, uses default.
            generate_report: Whether to generate an HTML report of the chunking
            report_path: Path where to save the report if generated
        """
        chunking_config = config or self._get_config_for_document_type(
            extracted_content.metadata.document_type
        )
        
        text_splitter = chunking_config.get_splitter()
        chunks: List[VectorChunk] = []
        
        # Process each section and its segments
        for section in extracted_content.metadata.sections:
            for segment in section.segments:
                
                text_chunks = text_splitter.split_text(segment.text)
                
                for chunk_index, chunk_text in enumerate(text_chunks):
                    # Get base metadata from reference
                    chunk_metadata = self.metadata_service.create_chunk_metadata(
                        object_metadata=object_metadata,
                        chunk_index=chunk_index,
                        content_metadata={
                            "document_type": extracted_content.metadata.document_type,
                            "title": extracted_content.metadata.title,
                            "author": extracted_content.metadata.author,
                            "creation_date": extracted_content.metadata.creation_date,
                            "language": extracted_content.metadata.language,
                            "section_heading": section.heading,
                            "section_index": section.section_index,
                            "segment_type": segment.segment_type,
                            "segment_index": segment.segment_index,
                            **segment.metadata,
                            "total_chunks": len(text_chunks)
                        },
                        chunk_text=chunk_text
                    )
                    
                    # Enrich metadata with additional context
                    chunk_metadata = self.metadata_service.enrich_chunk_metadata(
                        chunk_metadata,
                        chunk_text
                    )
                    
                    chunks.append(VectorChunk(
                        text=chunk_text,
                        object_id=object_id,
                        user_id=user_id,
                        metadata=chunk_metadata
                    ))
        
        if generate_report and report_path:
            self.report_service.generate_report(
                chunks=chunks,
                output_path=report_path,
                title=f"Chunking Report for {object_id}"
            )
        
        return chunks

    def _get_config_for_document_type(self, doc_type: DocumentType) -> ChunkingConfig:
        """Returns optimal chunking configuration based on document type"""
        configs = {
            DocumentType.PDF: ChunkingConfig(
                chunk_size=500,
                chunk_overlap=50,
                splitter_type="recursive"
            ),
            DocumentType.DOCX: ChunkingConfig(
                chunk_size=500,
                chunk_overlap=50,
                splitter_type="recursive"
            ),
            DocumentType.TXT: ChunkingConfig(
                chunk_size=500,
                chunk_overlap=50,
                splitter_type="recursive"
            ),
            DocumentType.PYTHON: ChunkingConfig(
                chunk_size=300,
                chunk_overlap=30,
                splitter_type="code"
            ),
            DocumentType.MARKDOWN: ChunkingConfig(
                chunk_size=500,
                chunk_overlap=50,
                splitter_type="markdown"
            ),
            # DocumentType.HTML: ChunkingConfig(
            #     chunk_size=500,
            #     chunk_overlap=50,
            #     splitter_type="html"
            # )
        }
        return configs.get(doc_type, self.default_config)

    async def create_conversation_chunks(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        splitter_type: SplitterType = "recursive"
    ) -> List[str]:
        """
        Creates chunks from conversation text, optimized for conversation flow
        
        Args:
            text: The conversation text to chunk
            chunk_size: Maximum size of each chunk in tokens
            chunk_overlap: Number of overlapping tokens between chunks
            splitter_type: Type of splitter to use
        """
        config = ChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            splitter_type=splitter_type,
            # Use conversation-appropriate separators
            separators=["\n\nUser:", "\n\nAssistant:", "\nUser:", "\nAssistant:", "\n\n", "\n", " ", ""]
        )
        
        text_splitter = config.get_splitter()
        chunks = text_splitter.split_text(text)
        
        # Validate chunk sizes
        validated_chunks = []
        for chunk in chunks:
            chunk_tokens = await LLMService.count_tokens(
                text=chunk,
                provider=LLMProvider.GTE_SMALL
            )
            if chunk_tokens > chunk_size:
                # If a chunk is still too large, split it further with smaller separators
                sub_config = ChunkingConfig(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    splitter_type="recursive",
                    separators=[". ", ", ", " ", ""]
                )
                sub_splitter = sub_config.get_splitter()
                validated_chunks.extend(sub_splitter.split_text(chunk))
            else:
                validated_chunks.append(chunk)
        
        # Validate the sub-split chunks one more time
        final_chunks = []
        for chunk in validated_chunks:
            chunk_tokens = await LLMService.count_tokens(
                text=chunk,
                provider=LLMProvider.GTE_SMALL
            )
            if chunk_tokens <= chunk_size:
                final_chunks.append(chunk)
            else:
                # Force split by characters if all else fails
                forced_splitter = ChunkingConfig(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    splitter_type="character"
                ).get_splitter()
                final_chunks.extend(forced_splitter.split_text(chunk))
        
        return final_chunks