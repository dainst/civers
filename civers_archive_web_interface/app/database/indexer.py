"""
Filesystem indexer for populating SQLite database from archived files.

Scans the filesystem storage and populates the SQLite database with
URLs, snapshots, and artifacts for fast querying.
"""

import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Callable, Optional

from ..models.url import ArchivedUrl
from ..models.snapshot import Snapshot
from .sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)


class FilesystemIndexer:
    """Indexes filesystem archives into SQLite database."""

    def __init__(
        self,
        db_manager: SQLiteManager,
        fs_provider=None
    ):
        """
        Initialize filesystem indexer.

        Args:
            db_manager: SQLite database manager
            fs_provider: Filesystem storage provider for scanning (optional,
                         required only for rebuild_index)
        """
        self.db = db_manager
        self.fs_provider = fs_provider

    @staticmethod
    def extract_request_id_from_snapshot_id(snapshot_id: str) -> Optional[str]:
        """
        Extract the original request_id from a snapshot_id.

        Snapshot IDs follow the pattern: req_{request_id}_{YYYYMMDD_HHMMSS}
        For example: req_test-123_20251211_135101 -> test-123

        Args:
            snapshot_id: The full snapshot ID

        Returns:
            The extracted request_id, or None if pattern doesn't match
        """
        # Pattern: req_{request_id}_{YYYYMMDD}_{HHMMSS}
        # The request_id can contain letters, numbers, hyphens, underscores
        # The timestamp is always in format YYYYMMDD_HHMMSS (15 chars including underscore)
        pattern = r'^req_(.+)_(\d{8}_\d{6})$'
        match = re.match(pattern, snapshot_id)

        if match:
            request_id = match.group(1)
            logger.debug(f"Extracted request_id '{request_id}' from snapshot_id '{snapshot_id}'")
            return request_id

        logger.warning(f"Could not extract request_id from snapshot_id: {snapshot_id}")
        return None

    def rebuild_index(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """
        Rebuild entire database from filesystem.

        Clears existing database and re-indexes all archives from filesystem.

        Args:
            progress_callback: Optional callback(current, total, message) for progress

        Returns:
            Statistics dict with counts: {urls, snapshots, artifacts, errors}
        """
        logger.info("Starting full index rebuild")
        stats = {'urls': 0, 'snapshots': 0, 'artifacts': 0, 'errors': 0}

        if self.fs_provider is None:
            raise RuntimeError("Cannot rebuild index without a filesystem provider")

        try:
            # Clear existing data
            with self.db.transaction():
                self.db.execute_query("DELETE FROM artifacts")
                self.db.execute_query("DELETE FROM snapshots")
                self.db.execute_query("DELETE FROM urls")

            # Scan filesystem to get all URLs
            all_urls = self.fs_provider.get_all_urls()
            total_urls = len(all_urls)

            logger.info(f"Found {total_urls} URLs to index")

            # Index each URL
            for idx, (url_id, archived_url) in enumerate(all_urls.items()):
                if progress_callback:
                    progress_callback(idx + 1, total_urls, f"Indexing {url_id}")

                try:
                    self._index_url(archived_url)
                    stats['urls'] += 1
                    stats['snapshots'] += len(archived_url.snapshots)
                except Exception as e:
                    logger.error(f"Failed to index {url_id}: {e}")
                    stats['errors'] += 1

            # Count artifacts
            cursor = self.db.execute_query("SELECT COUNT(*) as count FROM artifacts")
            result = cursor.fetchone()
            stats['artifacts'] = result[0] if result else 0

            logger.info(f"Index rebuild complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Index rebuild failed: {e}")
            raise

    def _index_url(self, archived_url: ArchivedUrl) -> None:
        """
        Index single URL with all its snapshots.

        Args:
            archived_url: ArchivedUrl object to index
        """
        with self.db.transaction():
            # Insert or replace URL record
            self.db.execute_query("""
                INSERT OR REPLACE INTO urls
                (url_id, original_url, folder_name, first_captured,
                 last_captured, snapshot_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                archived_url.url_id,
                str(archived_url.original_url),
                archived_url.folder_name,
                archived_url.first_captured.isoformat() if archived_url.first_captured else None,
                archived_url.last_captured.isoformat() if archived_url.last_captured else None,
                archived_url.snapshot_count,
                datetime.now().isoformat()
            ))

            # Index all snapshots with extracted request_id
            for snapshot in archived_url.snapshots:
                # Extract request_id from snapshot_id for deduplication support
                request_id = self.extract_request_id_from_snapshot_id(snapshot.snapshot_id)
                self._index_snapshot(snapshot, archived_url.url_id, request_id=request_id)

    def _index_snapshot(
        self,
        snapshot: Snapshot,
        url_id: str,
        request_id: str = None
    ) -> None:
        """
        Index single snapshot with its artifacts.

        Args:
            snapshot: Snapshot object to index
            url_id: Parent URL ID
            request_id: Original request ID for deduplication (optional)
        """
        # Extract metadata fields
        metadata_json = json.dumps(snapshot.metadata) if snapshot.metadata else None
        status_code = snapshot.metadata.get('status') if snapshot.metadata else None
        content_type = snapshot.metadata.get('content_type') if snapshot.metadata else None
        content_length = snapshot.metadata.get('content_length') if snapshot.metadata else None

        # Insert or replace snapshot record (now includes request_id)
        self.db.execute_query("""
            INSERT OR REPLACE INTO snapshots
            (snapshot_id, url_id, request_id, timestamp, url, title, folder_path,
             status_code, content_type, content_length, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.snapshot_id,
            url_id,
            request_id,
            snapshot.timestamp.isoformat(),
            str(snapshot.url),
            snapshot.title,
            snapshot.folder_path,
            status_code,
            content_type,
            content_length,
            metadata_json
        ))

        # Index artifacts (use INSERT OR IGNORE to preserve existing artifacts)
        for artifact_type in snapshot.available_artifacts:
            artifact_path = Path(snapshot.folder_path) / artifact_type
            file_size = artifact_path.stat().st_size if artifact_path.exists() else None

            self.db.execute_query("""
                INSERT OR IGNORE INTO artifacts
                (snapshot_id, artifact_type, file_path, file_size)
                VALUES (?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                artifact_type,
                str(artifact_path),
                file_size
            ))

    def index_new_snapshot(
        self,
        snapshot: Snapshot,
        url_id: str,
        request_id: str = None
    ) -> None:
        """
        Incrementally index newly created snapshot.

        Called by SQLiteStorageProvider after creating snapshot.

        Args:
            snapshot: Newly created snapshot
            url_id: URL ID for this snapshot
            request_id: Original request ID for deduplication (optional)
        """
        logger.debug(f"Indexing new snapshot {snapshot.snapshot_id}")

        try:
            with self.db.transaction():
                # Check if URL exists
                url_exists = self.db.fetch_one(
                    "SELECT 1 FROM urls WHERE url_id = ?",
                    (url_id,)
                )

                if not url_exists:
                    # Create new URL record
                    # Extract folder_name from snapshot folder_path
                    # folder_path format: archives/domain/path/snapshot_id
                    folder_parts = Path(snapshot.folder_path).parts
                    if len(folder_parts) >= 3:
                        folder_name = '/'.join(folder_parts[-3:-1])
                    else:
                        folder_name = url_id

                    self.db.execute_query("""
                        INSERT INTO urls
                        (url_id, original_url, folder_name, first_captured,
                         last_captured, snapshot_count)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (
                        url_id,
                        str(snapshot.url),
                        folder_name,
                        snapshot.timestamp.isoformat(),
                        snapshot.timestamp.isoformat()
                    ))
                else:
                    # Update existing URL record
                    self.db.execute_query("""
                        UPDATE urls
                        SET last_captured = MAX(last_captured, ?),
                            snapshot_count = snapshot_count + 1,
                            updated_at = ?
                        WHERE url_id = ?
                    """, (
                        snapshot.timestamp.isoformat(),
                        datetime.now().isoformat(),
                        url_id
                    ))

                # Index the snapshot with request_id
                self._index_snapshot(snapshot, url_id, request_id=request_id)

            logger.info(f"Indexed snapshot {snapshot.snapshot_id}")

        except Exception as e:
            logger.error(f"Failed to index snapshot: {e}")
            raise

    def add_artifacts_to_snapshot(
        self,
        snapshot: Snapshot,
        new_artifact_types: list
    ) -> None:
        """
        Add new artifacts to an existing snapshot.

        Called by SQLiteStorageProvider when adding files to existing snapshot.
        Does NOT increment snapshot_count since we're updating, not creating.

        Args:
            snapshot: Snapshot object (with existing snapshot_id)
            new_artifact_types: List of new artifact type names to add
        """
        logger.debug(
            f"Adding {len(new_artifact_types)} artifacts to snapshot {snapshot.snapshot_id}"
        )

        try:
            with self.db.transaction():
                for artifact_type in new_artifact_types:
                    artifact_path = Path(snapshot.folder_path) / artifact_type
                    file_size = artifact_path.stat().st_size if artifact_path.exists() else None

                    # Use INSERT OR IGNORE to avoid duplicates
                    self.db.execute_query("""
                        INSERT OR IGNORE INTO artifacts
                        (snapshot_id, artifact_type, file_path, file_size)
                        VALUES (?, ?, ?, ?)
                    """, (
                        snapshot.snapshot_id,
                        artifact_type,
                        str(artifact_path),
                        file_size
                    ))

            logger.info(
                f"Added {len(new_artifact_types)} artifacts to snapshot {snapshot.snapshot_id}: "
                f"{', '.join(new_artifact_types)}"
            )

        except Exception as e:
            logger.error(f"Failed to add artifacts to snapshot: {e}")
            raise
