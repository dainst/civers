"""
Snapshot model for representing individual snapshots of archived URLs.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from .artifact import Artifact


class Snapshot(BaseModel):
    """
    Represents a single snapshot of a URL at a specific point in time.
    
    This model corresponds to a timestamp directory in the storage structure
    and contains metadata about the archived content and available artifacts.
    """
    
    snapshot_id: str = Field(
        ...,
        description="Snapshot identifier (e.g., '20240315T143022Z' or 'req_test-request-1_20250904_061411')",
        min_length=1
    )
    
    timestamp: datetime = Field(
        ...,
        description="When this snapshot was captured (ISO format)"
    )
    
    url: HttpUrl = Field(
        ...,
        description="The URL that was archived"
    )
    
    title: Optional[str] = Field(
        None,
        description="Page title from metadata",
        max_length=500
    )
    
    folder_path: Optional[str] = Field(
        None,
        description="Path to snapshot directory in storage",
        exclude=True  # Don't expose internal paths in API
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata from metadata.json"
    )
    
    available_artifacts: List[str] = Field(
        default_factory=list,
        description="List of available artifact files for this snapshot"
    )
    
    artifacts: Optional[List[Artifact]] = Field(
        None,
        description="Detailed artifact information (populated when needed)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "snapshot_id": "20240315T143022Z",
                "timestamp": "2024-03-15T14:30:22Z",
                "url": "https://example.com",
                "title": "Example Domain",
                "metadata": {
                    "status": 200,
                    "content_type": "text/html",
                    "content_length": 1256
                },
                "available_artifacts": ["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]
            }
        }
    )
    
    @field_validator('snapshot_id')
    @classmethod
    def validate_snapshot_id_format(cls, v):
        """Validate snapshot ID matches request-timestamp format."""
        # Support both new request format and legacy timestamp format
        if v.startswith('req_'):
            # New format: req_{request_id}_{YYYYMMDD_HHMMSS}
            if len(v) < 10:  # Minimum length check
                raise ValueError('snapshot_id must be valid request format (req_{id}_{timestamp})')
        else:
            if len(v) != 16:
                raise ValueError('snapshot_id must be 16 characters (YYYYMMDDTHHMMSSZ) or request format (req_{id}_{timestamp})')
            
            try:
                datetime.strptime(v, '%Y%m%dT%H%M%SZ')
            except ValueError:
                raise ValueError('snapshot_id must be valid timestamp format (YYYYMMDDTHHMMSSZ)')
        
        return v
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        """Parse timestamp from various formats."""
        if isinstance(v, str):
            # Try multiple formats
            formats = [
                '%Y-%m-%dT%H:%M:%SZ',      # ISO format
                '%Y-%m-%dT%H:%M:%S',       # ISO without Z
                '%Y%m%dT%H%M%SZ',          # Compact format
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            
            raise ValueError(f'Unable to parse timestamp: {v}')
        
        return v
    
    @field_validator('available_artifacts')
    @classmethod
    def deduplicate_artifacts(cls, v):
        """Remove duplicate artifacts from the list.
        
        Note: Artifact type validation happens at the upload/API layer using
        config.validation.allowed_artifact_types. Models just hold data.
        """
        return list(set(v)) if v else []

    
    @field_validator('metadata')
    @classmethod
    def validate_metadata_structure(cls, v):
        """Validate metadata contains expected fields."""
        if not isinstance(v, dict):
            return {}
        
        # Ensure certain fields are properly typed
        if 'status' in v and not isinstance(v['status'], int):
            try:
                v['status'] = int(v['status'])
            except (ValueError, TypeError):
                del v['status']
        
        if 'content_length' in v and not isinstance(v['content_length'], int):
            try:
                v['content_length'] = int(v['content_length'])
            except (ValueError, TypeError):
                del v['content_length']
        
        return v
    
    @property
    def formatted_timestamp(self) -> str:
        """Human-readable timestamp."""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    @property
    def date_only(self) -> str:
        """Date portion only."""
        return self.timestamp.strftime('%Y-%m-%d')
    
    @property
    def time_only(self) -> str:
        """Time portion only."""
        return self.timestamp.strftime('%H:%M:%S')
    
    @property
    def artifact_count(self) -> int:
        """Number of available artifacts."""
        return len(self.available_artifacts)
    
    @property
    def has_wacz(self) -> bool:
        """Check if WACZ file is available."""
        return 'archive.wacz' in self.available_artifacts
    
    @property
    def has_warc(self) -> bool:
        """Check if WARC file is available."""
        return 'archive.warc' in self.available_artifacts
    
    @property
    def has_screenshot(self) -> bool:
        """Check if screenshot is available."""
        return 'screenshot.png' in self.available_artifacts
    
    @property
    def has_singlefile(self) -> bool:
        """Check if SingleFile HTML is available."""
        return 'singlefile.html' in self.available_artifacts
    
    @property
    def has_document(self) -> bool:
        """Check if document HTML is available.""" 
        return 'document.html' in self.available_artifacts
    
    @property
    def status_code(self) -> Optional[int]:
        """HTTP status code from metadata."""
        return self.metadata.get('status')
    
    @property
    def content_type(self) -> Optional[str]:
        """Content type from metadata."""
        return self.metadata.get('content_type')
    
    @property
    def content_length(self) -> Optional[int]:
        """Content length from metadata."""
        return self.metadata.get('content_length')
    
    def get_artifact_path(self, artifact_type: str) -> Optional[Path]:
        """Get full path to specific artifact file."""
        if not self.folder_path or artifact_type not in self.available_artifacts:
            return None
        
        return Path(self.folder_path) / artifact_type
    
    def has_artifact(self, artifact_type: str) -> bool:
        """Check if specific artifact is available."""
        return artifact_type in self.available_artifacts
    
    @classmethod
    def from_scanner_result(cls, scanner_snapshot):
        """
        Convert scanner Snapshot dataclass to Pydantic model.
        
        Args:
            scanner_snapshot: Snapshot object from storage scanner
            
        Returns:
            Snapshot Pydantic model
        """
        return cls(
            snapshot_id=scanner_snapshot.snapshot_id,
            timestamp=scanner_snapshot.timestamp,
            url=scanner_snapshot.url,
            title=scanner_snapshot.title,
            folder_path=str(scanner_snapshot.folder_path),
            metadata=scanner_snapshot.metadata or {},
            available_artifacts=scanner_snapshot.available_artifacts or []
        )