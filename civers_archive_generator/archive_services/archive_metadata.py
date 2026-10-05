"""Build and save capture metadata."""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiofiles

from archive_generators import ArtifactResult, ArtifactStatus
from domain.artifacts import ArchiveBundle


class ArchiveMetadata:
    """Build capture metadata and save it as JSON."""

    FILENAME = "archive_generator_metadata.json"

    def build(
        self,
        bundle: ArchiveBundle,
        artifacts: List[ArtifactResult],
        started_at: datetime,
        processing_time_seconds: float,
        generator_info: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Describe artifact results and files from the supplied bundle.

        processing_time_seconds is the elapsed time provided by the caller.
        """
        completed_at = started_at + timedelta(seconds=processing_time_seconds)

        return {
            'archive_info': {
                'url': bundle.url,
                'request_id': bundle.request_id,
                'created_at': started_at.isoformat(),
                'completed_at': completed_at.isoformat(),
                'processing_time_seconds': processing_time_seconds,
            },
            'artifacts_created': [a.name for a in artifacts if a.status == ArtifactStatus.SUCCESS],
            'failed_artifacts': [a.name for a in artifacts if a.status == ArtifactStatus.FAILED],
            'generator_info': generator_info,
            'files': [
                {
                    'name': f.name,
                    'size': f.size,
                    'created': f.created.isoformat(),
                }
                for f in bundle.files
            ],
        }

    async def save(self, metadata: Dict[str, Any], output_folder: str) -> None:
        """Write metadata to FILENAME inside the capture folder."""
        meta_path = os.path.join(output_folder, self.FILENAME)
        content = json.dumps(metadata, indent=2, ensure_ascii=False)
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(content)
