"""
Extraction result data model for metadata extraction services.
"""

from dataclasses import dataclass, field
from typing import Any

from models import IntermediateMetadata


@dataclass
class ExtractionResult:
    """
    Comprehensive result container for metadata extraction operations.

    This class encapsulates all information about a metadata extraction attempt,
    including success/failure status, extracted metadata, timing information,
    error details, and generated artifacts.
    """

    success: bool
    request_id: str
    processing_time_seconds: float
    source_url: str | None

    # Success case fields
    intermediate_metadata: IntermediateMetadata | None = None
    domain_used: str | None = None
    mappers_used: list[str] = field(default_factory=list)
    artifacts_created: list[str] = field(default_factory=list)
    json_output_path: str | None = None

    # Error case fields
    error_message: str | None = None
    error_type: str | None = None
    failed_stage: str | None = None

    # Quality metrics (for future use)
    quality_score: float | None = None
    completeness_score: float | None = None
    accuracy_score: float | None = None
    consistency_score: float | None = None
    validation_results: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for Kafka transport compatibility."""
        return {
            "success": self.success,
            "request_id": self.request_id,
            "processing_time_seconds": self.processing_time_seconds,
            "intermediate_metadata": self.intermediate_metadata.model_dump()
            if self.intermediate_metadata
            else None,
            "domain_used": self.domain_used,
            "mappers_used": self.mappers_used,
            "artifacts_created": self.artifacts_created,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "failed_stage": self.failed_stage,
            "quality_score": self.quality_score,
            "completeness_score": self.completeness_score,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "raw_data": self.raw_data,
        }

    @classmethod
    def success_result(
        cls,
        request_id: str,
        processing_time: float,
        intermediate_metadata: IntermediateMetadata,
        domain_used: str,
        mappers_used: list[str] | None = None,
        artifacts_created: list[str] | None = None,
        source_url: str | None = None,
    ) -> "ExtractionResult":
        """Create successful extraction result."""
        return cls(
            success=True,
            request_id=request_id,
            processing_time_seconds=processing_time,
            intermediate_metadata=intermediate_metadata,
            domain_used=domain_used,
            mappers_used=mappers_used or [],
            artifacts_created=artifacts_created or [],
            source_url=source_url,
        )

    @classmethod
    def failure_result(
        cls,
        request_id: str,
        processing_time: float,
        error_message: str,
        error_type: str = "UnknownError",
        failed_stage: str = "unknown",
        source_url: str | None = None,
        raw_data: dict[str, Any] | None = None,
    ) -> "ExtractionResult":
        """Create failed extraction result."""
        return cls(
            success=False,
            request_id=request_id,
            processing_time_seconds=processing_time,
            error_message=error_message,
            error_type=error_type,
            failed_stage=failed_stage,
            source_url=source_url,
            raw_data=raw_data or {},
        )
