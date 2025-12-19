"""
ArchivedUrl model for representing archived URLs with their snapshots.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from .snapshot import Snapshot


class ArchivedUrl(BaseModel):
    """
    Represents an archived URL with metadata and associated snapshots.
    
    This model corresponds to a URL directory in the storage structure
    and contains all snapshots captured for that URL.
    """
    
    url_id: str = Field(
        ...,
        description="Filesystem-safe identifier for the URL (e.g., 'example_com')",
        min_length=1,
        max_length=255
    )
    
    original_url: HttpUrl = Field(
        ...,
        description="The original URL that was archived (e.g., 'https://example.com')"
    )
    
    folder_name: str = Field(
        ...,
        description="Directory name in storage filesystem",
        min_length=1,
        max_length=255
    )
    
    snapshots: List[Snapshot] = Field(
        default_factory=list,
        description="List of snapshots for this URL, sorted by timestamp (newest first)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url_id": "example_com",
                "original_url": "https://example.com",
                "folder_name": "example_com",
                "snapshots": [
                    {
                        "snapshot_id": "20240315T143022Z",
                        "timestamp": "2024-03-15T14:30:22Z",
                        "url": "https://example.com",
                        "title": "Example Domain",
                        "available_artifacts": ["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]
                    }
                ]
            }
        }
    )
    
    @field_validator('url_id')
    @classmethod
    def validate_url_id(cls, v):
        """Validate URL ID format for filesystem safety."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('url_id must contain only alphanumeric characters, underscores, and hyphens')
        return v
    
    @field_validator('original_url', mode='before')
    @classmethod
    def validate_original_url(cls, v):
        """Ensure URL has proper scheme."""
        if isinstance(v, str) and not v.startswith(('http://', 'https://')):
            return f'https://{v}'
        return v
    
    @field_validator('snapshots')
    @classmethod
    def sort_snapshots_by_timestamp(cls, v):
        """Ensure snapshots are sorted by timestamp (newest first)."""
        if v:
            return sorted(v, key=lambda s: s.timestamp, reverse=True)
        return v
    
    @property
    def snapshot_count(self) -> int:
        """Number of snapshots for this URL."""
        return len(self.snapshots)
    
    @property 
    def first_captured(self) -> Optional[datetime]:
        """Timestamp of the earliest snapshot."""
        if not self.snapshots:
            return None
        return min(snapshot.timestamp for snapshot in self.snapshots)
    
    @property
    def last_captured(self) -> Optional[datetime]:
        """Timestamp of the most recent snapshot.""" 
        if not self.snapshots:
            return None
        return max(snapshot.timestamp for snapshot in self.snapshots)
    
    @property
    def date_range(self) -> Optional[str]:
        """Human-readable date range for snapshots."""
        if not self.snapshots:
            return None
        
        if self.snapshot_count == 1:
            return self.first_captured.strftime('%Y-%m-%d')
        
        first = self.first_captured.strftime('%Y-%m-%d')
        last = self.last_captured.strftime('%Y-%m-%d')
        
        if first == last:
            return first
        return f"{first} to {last}"
    
    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """Find a snapshot by its ID."""
        for snapshot in self.snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None
    
    def has_artifact_type(self, artifact_type: str) -> bool:
        """Check if any snapshot has the specified artifact type."""
        for snapshot in self.snapshots:
            if artifact_type in snapshot.available_artifacts:
                return True
        return False
    
    @classmethod
    def from_scanner_result(cls, scanner_archived_url):
        """
        Convert scanner ArchivedUrl dataclass to Pydantic model.
        
        Args:
            scanner_archived_url: ArchivedUrl object from storage scanner
            
        Returns:
            ArchivedUrl Pydantic model
        """
        from .snapshot import Snapshot
        
        snapshots = [
            Snapshot.from_scanner_result(scanner_snapshot)
            for scanner_snapshot in scanner_archived_url.snapshots
        ]
        
        return cls(
            url_id=scanner_archived_url.url_id,
            original_url=scanner_archived_url.original_url,
            folder_name=scanner_archived_url.folder_name,
            snapshots=snapshots
        )