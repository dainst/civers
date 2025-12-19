"""
Interface for metadata extraction services that handle web content metadata extraction.

This interface defines the contract for any metadata extraction service implementation,
enabling dependency injection and strategy pattern usage across the application.

NOTE: Configuration-related methods have been moved to ConfigDataModel where they belong.
This interface focuses purely on extraction functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from .extraction_result import ExtractionResult


class MetadataExtractionServiceInterface(ABC):
    """
    Interface for metadata extraction services that handle web content metadata extraction.
    
    This interface defines the contract for any metadata extraction service implementation,
    enabling dependency injection and strategy pattern usage across the application.
    Different implementations can provide varying extraction strategies, mappers,
    or optimization approaches while maintaining the same interface.
    
    CLEAN INTERFACE: Focuses only on extraction functionality.
    Configuration management is handled by ConfigDataModel.
    """

    @abstractmethod
    async def extract_metadata(
        self, 
        url: str, 
        request_id: str, 
        html_content: str = None,
        document_url: str = None
    ) -> ExtractionResult:
        """
        Extract metadata from document URL or provided HTML content.
        
        Content Sources (one required):
        1. document_url - Download HTML from this URL (e.g., storage service)
        2. html_content - Use provided HTML string
        
        Args:
            url: Source URL for context and validation
            request_id: Unique identifier for this request
            html_content: Optional HTML content (required if document_url not provided)
            document_url: Optional URL to download HTML from (required if html_content not provided)
            
        Returns:
            ExtractionResult containing:
                - success: bool - Whether extraction succeeded
                - intermediate_metadata: IntermediateMetadata - Extracted metadata (if successful)
                - request_id: str - Echo of the request ID
                - processing_time_seconds: float - Time taken to process
                - error_message: str - Error message (if failed)
                - error_type: str - Error type/category (if failed)
                - failed_stage: str - Stage where processing failed (if failed)
                - domain_used: str - Domain configuration that was used
                - mappers_used: List[str] - Mappers that successfully extracted data
                - artifacts_created: List[str] - Generated files/artifacts (JSON files, etc.)
                
        Raises:
            Exception: If extraction fails due to configuration or system errors
        """
        pass

    @abstractmethod
    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate if a URL can be processed by this extraction service.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing:
                - valid: bool - Whether URL is valid and supported
                - domain_supported: bool - Whether the domain has configuration
                - reason: str - Explanation if not valid/supported
        """
        pass


