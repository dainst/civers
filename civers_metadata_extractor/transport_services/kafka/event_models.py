"""
Event models for Kafka transport service.

These models define the structure of events exchanged via Kafka
for metadata extraction operations.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
import re
class EventBaseModel(BaseModel):
    request_id: str = Field(..., description="Unique identifier for the request")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        description="The timestamp when the event was created, in ISO 8601 UTC format"
    )
    url: str = Field(..., description="The URL associated with the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional request metadata")

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty request_id")
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        if isinstance(v, str):
            iso8601_utc_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            if not re.match(iso8601_utc_regex, v):
                raise ValueError("created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')")
        return v

    @field_validator("url")
    def validate_url(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty url")
        return v

class MetadataExtractionRequestEvent(EventBaseModel):
    """
    Event model for metadata extraction requests.
    
    Represents a request to extract metadata from a URL with enhanced workflow support.
    """
    domain: Optional[str] = Field(None, description="Domain configuration to use (if specific)")
    document_url: Optional[str] = Field(None, description="URL to download the HTML document from (e.g., storage service)")
    html_content: Optional[str] = Field(None, description="HTML content to process directly (used if document_url is not provided)")
    output_format: str = Field(default="json", description="Output format (json, xml)")
    output_directory: Optional[str] = Field(None, description="Custom output directory for generated files")
    include_quality_metrics: bool = Field(default=True, description="Include quality assessment in results")
    priority: int = Field(default=1, description="Processing priority (1=normal, 2=high, 3=urgent)")
    requester: Optional[str] = Field(None, description="Identifier of the requesting system/user")



class MetadataExtractionStatusEvent(EventBaseModel):
    """
    Event model for metadata extraction status updates.
    
    Provides status updates during metadata extraction processing.
    """
    status: str = Field(..., description="Current processing status (e.g. 'processing', 'completed', 'failed')")
    message: str = Field(..., description="Human-readable status message")
    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


class MetadataExtractionCompletedEvent(EventBaseModel):
    """
    Event model for successful metadata extraction completion.
    
    Contains the extracted metadata and comprehensive processing information.
    """
    extracted_metadata: Dict[str, Any] = Field(..., description="Extracted intermediate metadata")
    domain_used: str = Field(..., description="Domain configuration that was used")
    mappers_used: List[str] = Field(..., description="List of mappers that successfully extracted data")
    processing_time_seconds: float = Field(..., description="Total processing time in seconds")
    artifacts_created: List[str] = Field(default_factory=list, description="Generated files/artifacts")
    
    # Enhanced fields for complete workflow
    json_output_path: Optional[str] = Field(None, description="Path to generated JSON file")
    metadata_statistics: Dict[str, Any] = Field(default_factory=dict, description="Extraction statistics")
    quality_assessment: Optional[Dict[str, Any]] = Field(None, description="Quality metrics and scores")
    
    # Detailed extraction results
    extraction_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed extraction information")
    workflow_stages_completed: List[str] = Field(default_factory=list, description="Completed workflow stages")
    total_fields_extracted: int = Field(default=0, description="Total number of fields extracted")


class WorkflowProgressEvent(EventBaseModel):
    """Event for tracking workflow progress through stages."""
    stage: str = Field(..., description="Current workflow stage")
    stage_status: str = Field(..., description="Stage status (started, completed, failed)")
    progress_percentage: float = Field(..., ge=0, le=100, description="Overall progress percentage")
    current_operation: str = Field(..., description="Current operation description")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    stage_details: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific details")
    
    @field_validator("stage_status")
    @classmethod
    def validate_stage_status(cls, v: str) -> str:
        valid_statuses = ["started", "completed", "failed", "skipped"]
        if v not in valid_statuses:
            raise ValueError(f"stage_status must be one of {valid_statuses}")
        return v


class MetadataExtractionFailedEvent(EventBaseModel):
    """
    Event model for failed metadata extraction attempts.
    
    Contains error information and failure details.
    """

    error_message: str = Field(..., description="Error message describing the failure")
    error_type: str = Field(..., description="Type/category of error")
    error_code: Optional[str] = Field(None, description="Specific error code if applicable")
    failed_stage: Optional[str] = Field(None, description="Stage where processing failed (fetch, extract, map)")
    processing_time_seconds: Optional[float] = Field(None, description="Time spent before failure")
    retry_count: int = Field(default=0, description="Number of retry attempts made")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional failure details")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MetadataQualityEvent(EventBaseModel):
    """
    Event model for metadata quality assessment results.
    
    Provides quality metrics and validation results for extracted metadata.
    """
    quality_score: float = Field(..., ge=0, le=1, description="Overall quality score (0.0 to 1.0)")
    completeness_score: float = Field(..., ge=0, le=1, description="Completeness assessment")
    accuracy_score: float = Field(..., ge=0, le=1, description="Accuracy assessment")
    consistency_score: float = Field(..., ge=0, le=1, description="Consistency assessment")
    validation_results: Dict[str, Any] = Field(..., description="Detailed validation results")
    missing_fields: List[str] = Field(default_factory=list, description="Required fields that are missing")
    warnings: List[str] = Field(default_factory=list, description="Quality warnings")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchMetadataExtractionRequestEvent(EventBaseModel):
    """
    Event model for batch metadata extraction requests.
    
    Represents a request to extract metadata from multiple URLs.
    """
    batch_id: str = Field(..., description="Unique identifier for the batch")
    urls: List[str] = Field(..., min_length=1, description="List of URLs to process")
    domain: Optional[str] = Field(None, description="Domain configuration to use for all URLs")
    priority: int = Field(default=1, description="Processing priority for the batch")
    requester: Optional[str] = Field(None, description="Identifier of the requesting system/user")
    batch_options: Dict[str, Any] = Field(default_factory=dict, description="Batch processing options")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchMetadataExtractionStatusEvent(EventBaseModel):
    """
    Event model for batch metadata extraction status updates.
    """
    batch_id: str = Field(..., description="Batch identifier")
    total_urls: int = Field(..., description="Total number of URLs in the batch")
    completed_urls: int = Field(..., description="Number of URLs completed")
    failed_urls: int = Field(..., description="Number of URLs that failed")
    in_progress_urls: int = Field(..., description="Number of URLs currently being processed")
    status: str = Field(..., description="Overall batch status")
    progress: float = Field(..., ge=0, le=1, description="Batch progress (0.0 to 1.0)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional batch details")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Event type registry for easy reference
EVENT_TYPES = {
    'metadata_extraction_request': MetadataExtractionRequestEvent,
    'metadata_extraction_status': MetadataExtractionStatusEvent,
    'metadata_extraction_completed': MetadataExtractionCompletedEvent,
    'metadata_extraction_failed': MetadataExtractionFailedEvent,
    'workflow_progress': WorkflowProgressEvent,
    'metadata_quality': MetadataQualityEvent,
    'batch_metadata_extraction_request': BatchMetadataExtractionRequestEvent,
    'batch_metadata_extraction_status': BatchMetadataExtractionStatusEvent,
}


def create_event_from_dict(event_type: str, data: Dict[str, Any]) -> BaseModel:
    """
    Create an event instance from a dictionary.
    
    Args:
        event_type: Type of event to create
        data: Event data dictionary
        
    Returns:
        Event instance
        
    Raises:
        ValueError: If event_type is not recognized
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}. Available types: {list(EVENT_TYPES.keys())}")
    
    event_class = EVENT_TYPES[event_type]
    return event_class(**data)


def get_event_type_name(event: BaseModel) -> str:
    """
    Get the event type name for an event instance.
    
    Args:
        event: Event instance
        
    Returns:
        Event type name
        
    Raises:
        ValueError: If event type is not recognized
    """
    for event_type, event_class in EVENT_TYPES.items():
        if isinstance(event, event_class):
            return event_type
    
    raise ValueError(f"Unknown event instance type: {type(event)}")
