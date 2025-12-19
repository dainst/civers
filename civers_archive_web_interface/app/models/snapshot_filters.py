"""
Snapshot filtering and query parameter models.

This module provides Pydantic models for filtering snapshots by various criteria
including date ranges, artifact availability, and sorting options.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SnapshotSortOption(str, Enum):
    """Available sorting options for snapshot list."""
    TIMESTAMP_DESC = "timestamp"  # Newest first (default)
    TIMESTAMP_ASC = "timestamp_asc"  # Oldest first
    TITLE = "title"  # Alphabetical by title
    STATUS_CODE = "status_code"  # By HTTP status code


class SnapshotFilters(BaseModel):
    """Query parameters for filtering snapshots."""
    
    # Date range filtering
    from_date: Optional[datetime] = Field(
        None,
        description="Filter snapshots from this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"
    )
    
    to_date: Optional[datetime] = Field(
        None,
        description="Filter snapshots up to this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"
    )
    
    # Artifact availability filtering
    has_wacz: Optional[bool] = Field(
        None,
        description="Filter by WACZ file availability"
    )
    
    has_screenshot: Optional[bool] = Field(
        None,
        description="Filter by screenshot availability"
    )
    
    has_singlefile: Optional[bool] = Field(
        None,
        description="Filter by SingleFile HTML availability"
    )
    
    has_document: Optional[bool] = Field(
        None,
        description="Filter by document HTML availability"
    )
    
    # Status code filtering
    status_code: Optional[int] = Field(
        None,
        ge=100,
        le=599,
        description="Filter by HTTP status code (100-599)"
    )
    
    @field_validator('from_date', 'to_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Parse date from string if needed."""
        if isinstance(v, str):
            # Try multiple date formats
            formats = [
                '%Y-%m-%d',              # YYYY-MM-DD
                '%Y-%m-%dT%H:%M:%SZ',    # ISO with Z
                '%Y-%m-%dT%H:%M:%S',     # ISO without Z
            ]
            
            for fmt in formats:
                try:
                    parsed = datetime.strptime(v, fmt)
                    # Make timezone aware if it's not already
                    if parsed.tzinfo is None:
                        from datetime import timezone
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed
                except ValueError:
                    continue
            
            raise ValueError(f'Invalid date format: {v}. Use YYYY-MM-DD or ISO format')
        
        return v
    
    def applies_to_snapshot(self, snapshot) -> bool:
        """
        Check if snapshot matches all active filters.
        
        Args:
            snapshot: Snapshot object to check
            
        Returns:
            bool: True if snapshot passes all filters
        """
        # Date range filtering - handle timezone awareness
        if self.from_date:
            snapshot_dt = snapshot.timestamp
            filter_dt = self.from_date
            
            # Ensure both are timezone-aware or both are naive
            if snapshot_dt.tzinfo is not None and filter_dt.tzinfo is None:
                from datetime import timezone
                filter_dt = filter_dt.replace(tzinfo=timezone.utc)
            elif snapshot_dt.tzinfo is None and filter_dt.tzinfo is not None:
                filter_dt = filter_dt.replace(tzinfo=None)
            
            if snapshot_dt < filter_dt:
                return False
        
        if self.to_date:
            snapshot_dt = snapshot.timestamp
            filter_dt = self.to_date
            
            # Ensure both are timezone-aware or both are naive
            if snapshot_dt.tzinfo is not None and filter_dt.tzinfo is None:
                from datetime import timezone
                filter_dt = filter_dt.replace(tzinfo=timezone.utc)
            elif snapshot_dt.tzinfo is None and filter_dt.tzinfo is not None:
                filter_dt = filter_dt.replace(tzinfo=None)
            
            if snapshot_dt > filter_dt:
                return False
        
        # Artifact availability filtering
        if self.has_wacz is not None and snapshot.has_wacz != self.has_wacz:
            return False
        
        if self.has_screenshot is not None and snapshot.has_screenshot != self.has_screenshot:
            return False
        
        if self.has_singlefile is not None and snapshot.has_singlefile != self.has_singlefile:
            return False
        
        if self.has_document is not None and snapshot.has_document != self.has_document:
            return False
        
        # Status code filtering
        if self.status_code is not None and snapshot.status_code != self.status_code:
            return False
        
        return True


class SnapshotSummary(BaseModel):
    """
    Lightweight snapshot model for list responses.
    
    Contains essential fields without heavy metadata for better performance
    when returning large lists of snapshots.
    """
    
    snapshot_id: str = Field(
        ...,
        description="Snapshot identifier"
    )
    
    timestamp: datetime = Field(
        ...,
        description="When this snapshot was captured"
    )
    
    title: Optional[str] = Field(
        None,
        description="Page title from metadata"
    )
    
    available_artifacts: list[str] = Field(
        default_factory=list,
        description="List of available artifact files"
    )
    
    status_code: Optional[int] = Field(
        None,
        description="HTTP status code from metadata"
    )
    
    @classmethod
    def from_snapshot(cls, snapshot) -> 'SnapshotSummary':
        """
        Convert full Snapshot model to summary format.
        
        Args:
            snapshot: Full Snapshot object
            
        Returns:
            SnapshotSummary: Lightweight summary
        """
        return cls(
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            title=snapshot.title,
            available_artifacts=snapshot.available_artifacts,
            status_code=snapshot.status_code
        )
    
    @property
    def formatted_timestamp(self) -> str:
        """Human-readable timestamp."""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    @property
    def date_only(self) -> str:
        """Date portion only."""
        return self.timestamp.strftime('%Y-%m-%d')
    
    @property
    def artifact_count(self) -> int:
        """Number of available artifacts."""
        return len(self.available_artifacts)
    
    @property
    def has_wacz(self) -> bool:
        """Check if WACZ file is available."""
        return 'archive.wacz' in self.available_artifacts
    
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