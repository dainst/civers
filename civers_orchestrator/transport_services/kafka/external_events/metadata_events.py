"""
Metadata Extractor Event Models.

Copied from: civers_metadata_extractor/transport_services/kafka/event_models.py
These models define the events exchanged with the metadata_extractor service.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re


class EventBaseModel(BaseModel):
    """Base model for metadata extractor events."""

    request_id: str = Field(..., description="Unique identifier for the request")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        description="The timestamp when the event was created, in ISO 8601 UTC format",
    )
    url: str = Field(..., description="The URL associated with the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional request metadata")

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is not empty or whitespace."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty request_id")
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        """Validate created_at is in ISO 8601 UTC format."""
        if isinstance(v, str):
            iso8601_utc_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            if not re.match(iso8601_utc_regex, v):
                raise ValueError(
                    "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"
                )
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate url is not empty or whitespace."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty url")
        return v


class MetadataExtractionRequestEvent(EventBaseModel):
    """Event model for metadata extraction requests."""

    domain: Optional[str] = Field(
        None, description="Domain configuration to use (if specific)"
    )
    document_url: Optional[str] = Field(
        None, description="URL to download HTML document from (e.g., web interface artifact URL)"
    )
    html_content: Optional[str] = Field(
        None, description="HTML content to process (bypasses URL fetching)"
    )
    output_format: str = Field(default="json", description="Output format (json, xml)")
    output_directory: Optional[str] = Field(
        None, description="Custom output directory for generated files"
    )
    include_quality_metrics: bool = Field(
        default=True, description="Include quality assessment in results"
    )
    priority: int = Field(
        default=1, description="Processing priority (1=normal, 2=high, 3=urgent)"
    )
    requester: Optional[str] = Field(
        None, description="Identifier of the requesting system/user"
    )


class MetadataExtractionStatusEvent(EventBaseModel):
    """Event model for metadata extraction status updates."""

    status: str = Field(
        ...,
        description="Current processing status (e.g. 'processing', 'completed', 'failed')",
    )
    message: str = Field(..., description="Human-readable status message")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


class MetadataExtractionCompletedEvent(EventBaseModel):
    """Event model for successful metadata extraction completion."""

    extracted_metadata: Dict[str, Any] = Field(
        ..., description="Extracted intermediate metadata"
    )
    domain_used: str = Field(..., description="Domain configuration that was used")
    mappers_used: List[str] = Field(
        ..., description="List of mappers that successfully extracted data"
    )
    processing_time_seconds: float = Field(
        ..., description="Total processing time in seconds"
    )
    artifacts_created: List[str] = Field(
        default_factory=list, description="Generated files/artifacts"
    )

    # Enhanced fields for complete workflow
    json_output_path: Optional[str] = Field(
        None, description="Path to generated JSON file"
    )
    metadata_statistics: Dict[str, Any] = Field(
        default_factory=dict, description="Extraction statistics"
    )
    quality_assessment: Optional[Dict[str, Any]] = Field(
        None, description="Quality metrics and scores"
    )

    # Detailed extraction results
    extraction_details: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed extraction information"
    )
    workflow_stages_completed: List[str] = Field(
        default_factory=list, description="Completed workflow stages"
    )
    total_fields_extracted: int = Field(
        default=0, description="Total number of fields extracted"
    )


class MetadataExtractionFailedEvent(EventBaseModel):
    """Event model for failed metadata extraction attempts."""

    error_message: str = Field(..., description="Error message describing the failure")
    error_type: str = Field(..., description="Type/category of error")
    error_code: Optional[str] = Field(
        None, description="Specific error code if applicable"
    )
    failed_stage: Optional[str] = Field(
        None, description="Stage where processing failed (fetch, extract, map)"
    )
    processing_time_seconds: Optional[float] = Field(
        None, description="Time spent before failure"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts made")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional failure details"
    )
