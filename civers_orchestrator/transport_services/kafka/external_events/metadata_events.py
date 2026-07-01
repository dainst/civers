"""
Metadata Extractor Event Models.

These models define the events exchanged with the metadata_extractor service.
"""

from typing import Any

from pydantic import Field, field_validator

from transport_services.kafka.event_models import EventBaseModel


class MetadataExtractionRequestEvent(EventBaseModel):
    """Event model for metadata extraction requests."""

    domain: str | None = Field(
        None, description="Domain configuration to use (if specific)"
    )
    document_url: str | None = Field(
        None, description="URL to download HTML document from (e.g., web interface artifact URL)"
    )
    html_content: str | None = Field(
        None, description="HTML content to process (bypasses URL fetching)"
    )
    output_format: str = Field(default="json", description="Output format (json, xml)")
    output_directory: str | None = Field(
        None, description="Custom output directory for generated files"
    )
    include_quality_metrics: bool = Field(
        default=True, description="Include quality assessment in results"
    )
    priority: int = Field(
        default=1, description="Processing priority (1=normal, 2=high, 3=urgent)"
    )
    requester: str | None = Field(
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

    extracted_metadata: dict[str, Any] = Field(
        ..., description="Extracted intermediate metadata"
    )
    domain_used: str = Field(..., description="Domain configuration that was used")
    mappers_used: list[str] = Field(
        ..., description="List of mappers that successfully extracted data"
    )
    processing_time_seconds: float = Field(
        ..., description="Total processing time in seconds"
    )
    artifacts_created: list[str] = Field(
        default_factory=list, description="Generated files/artifacts"
    )

    # Enhanced fields for complete workflow
    json_output_path: str | None = Field(
        None, description="Path to generated JSON file"
    )
    metadata_statistics: dict[str, Any] = Field(
        default_factory=dict, description="Extraction statistics"
    )
    quality_assessment: dict[str, Any] | None = Field(
        None, description="Quality metrics and scores"
    )

    # Detailed extraction results
    extraction_details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed extraction information"
    )
    workflow_stages_completed: list[str] = Field(
        default_factory=list, description="Completed workflow stages"
    )
    total_fields_extracted: int = Field(
        default=0, description="Total number of fields extracted"
    )


class MetadataExtractionFailedEvent(EventBaseModel):
    """Event model for failed metadata extraction attempts."""

    error_message: str = Field(..., description="Error message describing the failure")
    error_type: str = Field(..., description="Type/category of error")
    error_code: str | None = Field(
        None, description="Specific error code if applicable"
    )
    failed_stage: str | None = Field(
        None, description="Stage where processing failed (fetch, extract, map)"
    )
    processing_time_seconds: float | None = Field(
        None, description="Time spent before failure"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts made")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional failure details"
    )
