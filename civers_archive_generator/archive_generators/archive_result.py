"""
Archive Result Data Classes.

This module defines structured result types for archive generation operations,
providing clear success/failure status and detailed artifact tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


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
    
    def validate_required_artifacts(
        self, 
        required_artifacts: List[str],
        artifact_name_mapping: Dict[str, List[str]] = None
    ) -> tuple:
        """
        Validate that required archive generator artifacts were successfully created.
        
        Note: This only validates artifacts that the ARCHIVE GENERATOR produces.
        Artifacts produced by other services (e.g., 'json' from metadata extractor)
        are skipped since this validation runs before those services execute.
        
        Args:
            required_artifacts: List of artifact names from domain config (e.g., ['warc', 'html', 'singlefile'])
            artifact_name_mapping: Optional mapping from domain config names to internal artifact names.
                                   If not provided, uses default mapping.
        
        Returns:
            Tuple of (is_valid: bool, missing_artifacts: List[str])
        """
        # Mapping from domain config artifact names to internal artifact names
        # ONLY includes artifacts that the archive generator produces
        # 'json' is NOT included - it's produced by the metadata extractor
        archive_generator_artifacts = {
            "warc": ["warc"],
            "html": ["dom-snapshot"],
            "screenshots": ["screenshot"],
            "singlefile": ["singlefile"],
        }
        
        mapping = artifact_name_mapping or archive_generator_artifacts
        missing = []
        
        for required in required_artifacts:
            # Skip artifacts not produced by the archive generator
            if required not in mapping:
                continue
            
            # Get internal artifact names for this required artifact
            internal_names = mapping.get(required)
            
            # Check if any of the internal names were successfully created
            found = False
            for internal_name in internal_names:
                artifact = self.get_artifact(internal_name)
                if artifact and artifact.is_success:
                    found = True
                    break
            
            if not found:
                missing.append(required)
        
        is_valid = len(missing) == 0
        return (is_valid, missing)

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
        snapshot_id: str = None,
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
            error_message=error_message,
            error_type=error_type,
            snapshot_id=snapshot_id,
            metadata=metadata
        )
