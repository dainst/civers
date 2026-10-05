"""Result types for a single generated artifact."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any


class ArtifactStatus(Enum):
    """Reported artifact outcome. The service detects missing results separately."""
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ArtifactResult:
    """Result for one requested artifact. file_size is measured in bytes."""
    name: str
    status: ArtifactStatus
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Return True if the artifact was generated."""
        return self.status == ArtifactStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "error": self.error,
            "metadata": self.metadata
        }
