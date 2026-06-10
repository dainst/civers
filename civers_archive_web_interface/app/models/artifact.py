"""
Artifact model for representing individual files in snapshots.
"""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

class Artifact(BaseModel):
    """
    Represents a single artifact file associated with a snapshot.
    
    Each artifact corresponds to a specific file type that can be
    generated or captured during the archiving process.
    
    Note: Artifact type validation happens at the upload/API layer using
    config.validation.allowed_artifact_types. This model just holds data.
    """
    
    artifact_type: str = Field(
        ...,
        description="Type of artifact file (e.g., 'archive.wacz', 'screenshot.png')"
    )
    
    filename: str = Field(
        ...,
        description="Name of the file in storage",
        min_length=1,
        max_length=255
    )
    
    file_path: Optional[str] = Field(
        None,
        description="Full path to the file in storage (internal use)",
        exclude=True  # Don't expose internal paths in API
    )
    
    size_bytes: Optional[int] = Field(
        None,
        description="File size in bytes",
        ge=0
    )
    
    exists: bool = Field(
        True,
        description="Whether the file actually exists in storage"
    )
    
    mime_type: Optional[str] = Field(
        None,
        description="MIME type of the file"
    )
    
    checksum: Optional[str] = Field(
        None,
        description="File checksum for integrity verification",
        max_length=64
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "artifact_type": "archive.wacz",
                "filename": "archive.wacz",
                "size_bytes": 1048576,
                "exists": True,
                "mime_type": "application/zip"
            }
        }
    )
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Validate filename for security."""
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('filename cannot contain path traversal characters')
        return v
    
    @property
    def formatted_size(self) -> str:
        """Human-readable file size."""
        if self.size_bytes is None:
            return "Unknown size"
        
        if self.size_bytes == 0:
            return "0 bytes"
        
        units = ['bytes', 'KB', 'MB', 'GB']
        size = float(self.size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    @property
    def is_viewable(self) -> bool:
        """Whether this artifact can be viewed in browser."""
        viewable_types = {
            'singlefile.html', 'document.html', 'screenshot.png', 'dom-snapshot.html'
        }
        return self.artifact_type in viewable_types
    
    @property
    def is_replayable(self) -> bool:
        """Whether this artifact can be replayed with ReplayWeb.page."""
        replayable_types = {'archive.warc', 'archive.wacz'}
        return self.artifact_type in replayable_types
    
    @property
    def download_filename(self) -> str:
        """Suggested filename for downloads."""
        return self.filename
    

    
    @classmethod
    def create_from_file(cls, artifact_type: str, file_path: Path) -> 'Artifact':
        """
        Creates an Artifact model from an actual file that exists on disk.
        
        Usage Example:
            from pathlib import Path
            from app.models import Artifact

            # Create artifact from actual file
            file_path = Path("storage/example_com/20240315T143022Z/archive.wacz")
            artifact = Artifact.create_from_file("archive.wacz", file_path)
            
        Args:
            artifact_type: Type of artifact as string
            file_path: Path to the file
            
        Returns:
            Artifact model with file information
        """
        exists = file_path.exists()
        size_bytes = file_path.stat().st_size if exists else None
        
        return cls(
            artifact_type=artifact_type,
            filename=file_path.name,
            file_path=str(file_path),
            size_bytes=size_bytes,
            exists=exists
        )
    
    @classmethod
    def create_missing(cls, artifact_type: str) -> 'Artifact':
        """
        Creates an Artifact model for a file that should exist but is missing.
        
        Args:
            artifact_type: Type of artifact as string
            
        Returns:
            Artifact model marked as not existing
        """
        return cls(
            artifact_type=artifact_type,
            filename=artifact_type,
            exists=False
        )