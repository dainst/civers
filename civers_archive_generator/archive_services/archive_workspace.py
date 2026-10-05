"""Create capture folders and list their files.

Folder layout: archives/example_com/about_us/req_abc123_20260831_120000
"""

import asyncio
import logging
import os
import stat
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from configs.models import ConfigDataModel
from domain.artifacts import ArchiveBundle, ArtifactFile

logger = logging.getLogger(__name__)

# File types by extension; unknown extensions use application/octet-stream.
_MEDIA_TYPES = {
    ".warc": "application/warc",
    ".wacz": "application/octet-stream",
    ".html": "text/html",
    ".png": "image/png",
    ".json": "application/json",
    ".log": "text/plain",
}
_UNKNOWN_MEDIA_TYPE = "application/octet-stream"

# Resolve relative archive directories from the service package.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class ArchiveWorkspace:
    """Capture folder and identity. open() creates the folder before returning it."""

    def __init__(self, path: Path, snapshot_id: str, url: str, request_id: str) -> None:
        self.path = path
        self.snapshot_id = snapshot_id
        self.url = url
        self.request_id = request_id

    @staticmethod
    def _domain_folder(host: str) -> str:
        """Turn a host into a folder name. Dots and hyphens both become underscores."""
        return host.replace(".", "_").replace("-", "_")

    @staticmethod
    def _page_folder(url_path: str) -> str:
        """Replace path separators and hyphens with underscores; keep dots.

        Use home_page for an empty URL path.
        """
        return url_path.strip("/").replace("/", "_").replace("-", "_") or "home_page"

    @staticmethod
    def _safe_request_id(request_id: str) -> str:
        """Keep letters, digits, hyphens and underscores from the request ID."""
        return "".join(c for c in request_id if c.isalnum() or c in "-_")

    @classmethod
    def _new_snapshot_id(cls, request_id: str) -> str:
        """Combine the request ID with the current timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"req_{cls._safe_request_id(request_id)}_{timestamp}"

    @classmethod
    def _folder_for(cls, archive_directory: str, url: str, snapshot_id: str) -> Path:
        """Build the capture path; resolve relative roots from the service package."""
        parsed = urlparse(url)
        host = parsed.hostname or parsed.netloc.split(":")[0]

        root = Path(archive_directory)
        if not root.is_absolute():
            root = _PACKAGE_ROOT / root

        return (
            root
            / cls._domain_folder(host)
            / cls._page_folder(parsed.path)
            / snapshot_id
        )

    @classmethod
    async def open(
        cls, config: ConfigDataModel, url: str, request_id: str
    ) -> "ArchiveWorkspace":
        """Create a capture folder and return its workspace."""
        snapshot_id = cls._new_snapshot_id(request_id)
        path = cls._folder_for(config.app.archive_directory, url, snapshot_id)

        # Create the folder without blocking other async tasks.
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
        logger.debug(f"📂 Opened archive workspace: {path}")

        return cls(path=path, snapshot_id=snapshot_id, url=url, request_id=request_id)

    @staticmethod
    def _media_type(name: str) -> str:
        """Look up the file type by extension."""
        return _MEDIA_TYPES.get(Path(name).suffix.lower(), _UNKNOWN_MEDIA_TYPE)

    @classmethod
    def _describe(cls, path: Path, info: os.stat_result) -> ArtifactFile:
        """Build a file record from the supplied filesystem information."""
        return ArtifactFile(
            name=path.name,
            path=path,
            size=info.st_size,
            media_type=cls._media_type(path.name),
            created=datetime.fromtimestamp(info.st_ctime),
        )

    def _scan(self) -> tuple[ArtifactFile, ...]:
        """List regular files directly in the capture folder; skip subfolders."""
        if not self.path.is_dir():
            raise FileNotFoundError(f"Archive folder does not exist: {self.path}")

        found = []
        for entry in sorted(self.path.iterdir()):
            info = entry.stat()
            if stat.S_ISREG(info.st_mode):
                found.append(self._describe(entry, info))
        return tuple(found)

    def _scan_one(self, path: Path) -> ArtifactFile:
        """Describe one regular file from the capture folder."""
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise FileNotFoundError(f"Not a file in the archive folder: {path}")
        return self._describe(path, info)

    async def inventory(self) -> ArchiveBundle:
        """Build an archive bundle from the folder, including logs.

        Storage backends choose which files to upload.
        """
        files = await asyncio.to_thread(self._scan)
        return ArchiveBundle(
            snapshot_id=self.snapshot_id,
            url=self.url,
            request_id=self.request_id,
            root=self.path,
            files=files,
        )

    async def stat_one(self, name: str) -> ArtifactFile:
        """Describe a newly written file without scanning the folder again."""
        return await asyncio.to_thread(self._scan_one, self.path / name)
