"""
Archive Result Data Classes.

This module defines structured result types for archive generation operations,
providing clear success/failure status and detailed artifact tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class ArtifactStatus(Enum):
    """Status of an individual artifact generation."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_REQUESTED = "not_requested"


@dataclass
class ArtifactResult:
    """
    Result of generating a single artifact (WARC, screenshot, DOM snapshot, etc.).
    
    Attributes:
        name: Artifact name/type (e.g., "warc", "screenshot", "dom-snapshot", "singlefile")
        status: Status of artifact generation
        file_path: Path to generated artifact file (if successful)
        file_size: Size of generated artifact in bytes (if successful)
        error: Error message if generation failed
        metadata: Additional artifact-specific metadata
    """
    name: str
    status: ArtifactStatus
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Check if artifact was successfully generated."""
        return self.status == ArtifactStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class ArchiveResult:
    """
    Structured result of an archive generation operation.
    
    This provides clear success/failure semantics and detailed tracking
    of individual artifacts. An archive is considered successful only if
    ALL requested artifacts were generated successfully.
    
    Attributes:
        success: True if ALL requested artifacts were generated successfully
        archive_path: Path to the archive directory
        request_id: Unique identifier for the archive request
        url: URL that was archived
        artifacts: List of individual artifact results
        processing_time_seconds: Total processing time
        scoop_exit_code: Exit code from Scoop CLI (if applicable)
        error_message: Overall error message if archive failed
        error_type: Type/category of error (for error handling)
        metadata: Additional archive metadata
    """
    success: bool
    archive_path: str
    request_id: str
    url: str
    artifacts: List[ArtifactResult] = field(default_factory=list)
    processing_time_seconds: float = 0.0
    scoop_exit_code: Optional[int] = None
    singlefile_exit_code: Optional[int] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    snapshot_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def successful_artifacts(self) -> List[ArtifactResult]:
        """Get list of successfully generated artifacts."""
        return [a for a in self.artifacts if a.is_success]
    
    @property
    def failed_artifacts(self) -> List[ArtifactResult]:
        """Get list of failed artifacts."""
        return [a for a in self.artifacts if a.status == ArtifactStatus.FAILED]
    
    @property
    def artifacts_created(self) -> List[str]:
        """Get list of successfully created artifact names (for compatibility)."""
        return [a.name for a in self.successful_artifacts]
    
    def get_artifact(self, name: str) -> Optional[ArtifactResult]:
        """Get artifact result by name."""
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None
    
    def add_artifact(self, artifact: ArtifactResult) -> None:
        """Add an artifact result."""
        self.artifacts.append(artifact)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/logging."""
        return {
            "success": self.success,
            "archive_path": self.archive_path,
            "request_id": self.request_id,
            "url": self.url,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "artifacts_created": self.artifacts_created,
            "processing_time_seconds": self.processing_time_seconds,
            "scoop_exit_code": self.scoop_exit_code,
            "singlefile_exit_code": self.singlefile_exit_code,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "snapshot_id": self.snapshot_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def create_success(
        cls,
        archive_path: str,
        request_id: str,
        url: str,
        artifacts: List[ArtifactResult],
        processing_time_seconds: float,
        scoop_exit_code: int = 0,
        snapshot_id: str = None,
        **metadata
    ) -> "ArchiveResult":
        """Factory method to create a successful archive result."""
        return cls(
            success=True,
            archive_path=archive_path,
            request_id=request_id,
            url=url,
            artifacts=artifacts,
            processing_time_seconds=processing_time_seconds,
            scoop_exit_code=scoop_exit_code,
            snapshot_id=snapshot_id,
            metadata=metadata
        )
    
    @classmethod
    def create_failure(
        cls,
        archive_path: str,
        request_id: str,
        url: str,
        error_message: str,
        error_type: str = "processing_error",
        artifacts: List[ArtifactResult] = None,
        processing_time_seconds: float = 0.0,
        scoop_exit_code: int = None,
        **metadata
    ) -> "ArchiveResult":
        """Factory method to create a failed archive result."""
        return cls(
            success=False,
            archive_path=archive_path,
            request_id=request_id,
            url=url,
            artifacts=artifacts or [],
            processing_time_seconds=processing_time_seconds,
            scoop_exit_code=scoop_exit_code,
            error_message=error_message,
            error_type=error_type,
            metadata=metadata
        )
