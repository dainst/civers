"""
Extraction result data model for metadata extraction services.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
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
    source_url: str
    
    # Success case fields
    intermediate_metadata: Optional[IntermediateMetadata] = None
    domain_used: Optional[str] = None
    mappers_used: List[str] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    json_output_path: Optional[str] = None
    
    # Error case fields
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    failed_stage: Optional[str] = None
    
    # Quality metrics (for future use)
    quality_score: Optional[float] = None
    completeness_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    consistency_score: Optional[float] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for Kafka transport compatibility."""
        return {
            'success': self.success,
            'request_id': self.request_id,
            'processing_time_seconds': self.processing_time_seconds,
            'intermediate_metadata': self.intermediate_metadata.model_dump() if self.intermediate_metadata else None,
            'domain_used': self.domain_used,
            'mappers_used': self.mappers_used,
            'artifacts_created': self.artifacts_created,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'failed_stage': self.failed_stage,
            'quality_score': self.quality_score,
            'completeness_score': self.completeness_score,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'raw_data': self.raw_data
        }
    
    @classmethod
    def success_result(
        cls,
        request_id: str,
        processing_time: float,
        intermediate_metadata: IntermediateMetadata,
        domain_used: str,
        mappers_used: List[str] = None,
        artifacts_created: List[str] = None,
        source_url: str = None
    ) -> 'ExtractionResult':
        """Create successful extraction result."""
        return cls(
            success=True,
            request_id=request_id,
            processing_time_seconds=processing_time,
            intermediate_metadata=intermediate_metadata,
            domain_used=domain_used,
            mappers_used=mappers_used or [],
            artifacts_created=artifacts_created or [],
            source_url=source_url
        )
    
    @classmethod
    def failure_result(
        cls,
        request_id: str,
        processing_time: float,
        error_message: str,
        error_type: str = "UnknownError",
        failed_stage: str = "unknown",
        source_url: str = None,
        raw_data: Dict[str, Any] = None
    ) -> 'ExtractionResult':
        """Create failed extraction result."""
        return cls(
            success=False,
            request_id=request_id,
            processing_time_seconds=processing_time,
            error_message=error_message,
            error_type=error_type,
            failed_stage=failed_stage,
            source_url=source_url,
            raw_data=raw_data or {}
        )