from typing import Dict, Any, List
from datetime import datetime
from content.models.source import Source

class MetadataService:
    @staticmethod
    def create_chunk_metadata(
        object_metadata: Dict[str, Any], 
        chunk_index: int,
        content_metadata: Dict[str, Any],
        chunk_text: str
    ) -> Dict[str, Any]:
        """
        Creates metadata for a vector chunk, combining reference metadata
        with content-specific metadata
        
        Args:
            reference: Business metadata from the Reference model
            chunk_index: Index of this chunk within its segment
            content_metadata: Document and segment metadata
            chunk_text: The text content of this chunk
        """
        # Start with reference (business) metadata
        metadata = {
            **object_metadata,  # Include all reference metadata
            
            # Document metadata
            "document_type": content_metadata["document_type"],
            "title": content_metadata["title"],
            "author": content_metadata["author"],
            "creation_date": content_metadata["creation_date"],
            "language": content_metadata["language"],
            
            # Section metadata
            "section_heading": content_metadata["section_heading"],
            "section_index": content_metadata["section_index"],
            
            # Segment metadata
            "segment_type": content_metadata["segment_type"],
            "segment_index": content_metadata["segment_index"],
            
            # Chunk metadata
            "chunk_index": chunk_index,
            "total_chunks": content_metadata["total_chunks"]
        }
        
        # Include any additional segment-specific metadata
        for key, value in content_metadata.items():
            if key not in metadata:
                metadata[key] = value

        return metadata

    @staticmethod
    def enrich_chunk_metadata(
        base_metadata: Dict[str, Any],
        chunk_text: str
    ) -> Dict[str, Any]:
        """
        Enriches chunk metadata with additional context
        like semantic markers, key entities, etc.
        """
        # TODO: Add semantic analysis, entity extraction, etc.
        return base_metadata 