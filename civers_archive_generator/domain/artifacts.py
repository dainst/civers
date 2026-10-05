"""Immutable file records and archive bundles shared with metadata and storage."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field


class ArtifactFile(BaseModel):
    """Saved file information: path, byte size, file type and filesystem timestamp."""

    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    size: int
    media_type: str
    created: datetime


class ArchiveBundle(BaseModel):
    """Capture identity and an immutable collection of saved files, including logs."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    url: str
    request_id: str
    root: Path
    files: tuple[ArtifactFile, ...] = ()

    def add(self, f: ArtifactFile) -> "ArchiveBundle":
        """Return a new bundle with one additional file."""
        return self.model_copy(update={"files": self.files + (f,)})

    @computed_field
    @property
    def total_size(self) -> int:
        """Return the combined size of all files in bytes."""
        return sum(f.size for f in self.files)
