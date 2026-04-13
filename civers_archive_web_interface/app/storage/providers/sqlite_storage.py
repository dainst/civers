"""
SQLite-based storage provider using database index.

Implements StorageProviderInterface using SQLite for fast queries
while storing actual files on filesystem. Completely separate from
FilesystemStorageProvider.
"""

import logging
import json
from typing import Dict, Optional, IO, Any
from pathlib import Path
from datetime import datetime

from .storage_provider_interface import StorageProviderInterface, StorageError
from ...models.url import ArchivedUrl
from ...models.snapshot import Snapshot
from ...database.sqlite_manager import SQLiteManager
from ...database.indexer import FilesystemIndexer
from ...utils.url_parser import parse_url, generate_request_id, build_storage_path
from ...utils.file_storage import store_snapshot_files
from configs.models import ValidationConfig

logger = logging.getLogger(__name__)


class SQLiteStorageProvider(StorageProviderInterface):
    """
    SQLite-based storage provider.

    Files stored on filesystem using shared utilities,
    queries use SQLite index for performance.
    SEPARATE from FilesystemStorageProvider.
    """

    def __init__(
        self,
        db_manager: SQLiteManager,
        storage_path: Path,
        validation_config: ValidationConfig
    ):
        """
        Initialize SQLite storage provider.

        Args:
            db_manager: SQLite database manager
            storage_path: Path to filesystem storage directory
            validation_config: Validation configuration
        """
        self.db = db_manager
        self.storage_path = Path(storage_path)
        self.validation_config = validation_config

    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        """
        Get all URLs from database using batch queries.

        Uses 3 flat queries instead of nested per-URL/per-snapshot queries
        to avoid N+1 query performance degradation.

        Returns:
            Dictionary mapping url_id to ArchivedUrl objects

        Raises:
            StorageError: If database query fails
        """
        try:
            # Query 1: All URLs
            url_rows = self.db.fetch_all("""
                SELECT url_id, original_url, folder_name,
                       first_captured, last_captured, snapshot_count
                FROM urls
                ORDER BY last_captured DESC
            """)

            # Query 2: All snapshots
            snapshot_rows = self.db.fetch_all("""
                SELECT snapshot_id, url_id, timestamp, url, title, folder_path,
                       status_code, content_type, content_length, metadata_json
                FROM snapshots
                ORDER BY timestamp DESC
            """)

            # Query 3: All artifacts
            artifact_rows = self.db.fetch_all("""
                SELECT snapshot_id, artifact_type
                FROM artifacts
            """)

            # Build lookup: snapshot_id -> [artifact_types]
            artifacts_by_snapshot = {}
            for row in artifact_rows:
                artifacts_by_snapshot.setdefault(row['snapshot_id'], []).append(row['artifact_type'])

            # Build lookup: url_id -> [Snapshot objects]
            snapshots_by_url = {}
            for snap_row in snapshot_rows:
                # Parse metadata
                metadata = {}
                if snap_row['metadata_json']:
                    try:
                        metadata = json.loads(snap_row['metadata_json'])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata for {snap_row['snapshot_id']}")

                snapshot = Snapshot(
                    snapshot_id=snap_row['snapshot_id'],
                    timestamp=datetime.fromisoformat(snap_row['timestamp']),
                    url=snap_row['url'],
                    title=snap_row['title'],
                    folder_path=snap_row['folder_path'],
                    metadata=metadata,
                    available_artifacts=artifacts_by_snapshot.get(snap_row['snapshot_id'], [])
                )
                snapshots_by_url.setdefault(snap_row['url_id'], []).append(snapshot)

            # Assemble final result
            result = {}
            for url_row in url_rows:
                archived_url = ArchivedUrl(
                    url_id=url_row['url_id'],
                    original_url=url_row['original_url'],
                    folder_name=url_row['folder_name'],
                    snapshots=snapshots_by_url.get(url_row['url_id'], [])
                )
                result[archived_url.url_id] = archived_url

            logger.debug(f"Retrieved {len(result)} URLs from database")
            return result

        except Exception as e:
            logger.error(f"Database query failed: {e}")
            raise StorageError(f"Database query failed: {str(e)}") from e

    def get_url_by_id(self, url_id: str) -> Optional[ArchivedUrl]:
        """
        Get specific URL from database.

        Args:
            url_id: The URL identifier

        Returns:
            ArchivedUrl object if found, None otherwise

        Raises:
            StorageError: If database query fails
        """
        try:
            # Query URL
            url_row = self.db.fetch_one("""
                SELECT url_id, original_url, folder_name,
                       first_captured, last_captured, snapshot_count
                FROM urls
                WHERE url_id = ?
            """, (url_id,))

            if not url_row:
                return None

            # Query snapshots for this URL
            snapshots = self._get_snapshots_for_url(url_id)

            # Build ArchivedUrl
            archived_url = ArchivedUrl(
                url_id=url_row['url_id'],
                original_url=url_row['original_url'],
                folder_name=url_row['folder_name'],
                snapshots=snapshots
            )

            return archived_url

        except Exception as e:
            logger.error(f"Failed to get URL {url_id}: {e}")
            raise StorageError(f"Failed to get URL: {str(e)}") from e

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """
        Get specific snapshot from database.

        Args:
            snapshot_id: The snapshot identifier

        Returns:
            Snapshot object if found, None otherwise

        Raises:
            StorageError: If database query fails
        """
        try:
            # Query snapshot
            snap_row = self.db.fetch_one("""
                SELECT snapshot_id, timestamp, url, title, folder_path,
                       status_code, content_type, content_length, metadata_json
                FROM snapshots
                WHERE snapshot_id = ?
            """, (snapshot_id,))

            if not snap_row:
                return None

            # Query artifacts
            artifact_rows = self.db.fetch_all("""
                SELECT artifact_type
                FROM artifacts
                WHERE snapshot_id = ?
            """, (snapshot_id,))

            available_artifacts = [row['artifact_type'] for row in artifact_rows]

            # Parse metadata
            metadata = {}
            if snap_row['metadata_json']:
                try:
                    metadata = json.loads(snap_row['metadata_json'])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for {snapshot_id}")

            # Build Snapshot
            snapshot = Snapshot(
                snapshot_id=snap_row['snapshot_id'],
                timestamp=datetime.fromisoformat(snap_row['timestamp']),
                url=snap_row['url'],
                title=snap_row['title'],
                folder_path=snap_row['folder_path'],
                metadata=metadata,
                available_artifacts=available_artifacts
            )

            return snapshot

        except Exception as e:
            logger.error(f"Failed to get snapshot {snapshot_id}: {e}")
            raise StorageError(f"Failed to get snapshot: {str(e)}") from e

    def get_artifact_stream(self, snapshot_id: str, artifact_type: str) -> Optional[IO]:
        """
        Get artifact file from filesystem.

        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact

        Returns:
            File stream if found, None otherwise

        Raises:
            StorageError: If operation fails
        """
        try:
            # Query artifact path from database
            result = self.db.fetch_one("""
                SELECT file_path
                FROM artifacts
                WHERE snapshot_id = ? AND artifact_type = ?
            """, (snapshot_id, artifact_type))

            if not result:
                return None

            # Open file from filesystem
            file_path = Path(result['file_path'])
            if not file_path.exists():
                logger.warning(f"Artifact file not found: {file_path}")
                return None

            return open(file_path, 'rb')

        except Exception as e:
            logger.error(f"Failed to get artifact stream: {e}")
            raise StorageError(f"Failed to get artifact stream: {str(e)}") from e

    def artifact_exists(self, snapshot_id: str, artifact_type: str) -> bool:
        """
        Check if artifact exists in database.

        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact

        Returns:
            True if artifact exists, False otherwise

        Raises:
            StorageError: If operation fails
        """
        try:
            result = self.db.fetch_one("""
                SELECT 1
                FROM artifacts
                WHERE snapshot_id = ? AND artifact_type = ?
            """, (snapshot_id, artifact_type))
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check artifact existence: {e}")
            return False

    def get_artifact_path(self, snapshot_id: str, artifact_type: str) -> Optional[Path]:
        """
        Get artifact path from database.

        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact

        Returns:
            Path to artifact if found, None otherwise

        Raises:
            StorageError: If operation fails
        """
        try:
            result = self.db.fetch_one("""
                SELECT file_path
                FROM artifacts
                WHERE snapshot_id = ? AND artifact_type = ?
            """, (snapshot_id, artifact_type))

            return Path(result['file_path']) if result else None

        except Exception as e:
            logger.error(f"Failed to get artifact path: {e}")
            return None

    def _find_existing_snapshot(self, request_id: str, url_id: str) -> Optional[Dict]:
        """
        Find an existing snapshot by request_id and url_id.

        Args:
            request_id: The original request identifier
            url_id: The URL identifier (domain_path)

        Returns:
            Snapshot row dict if found, None otherwise
        """
        try:
            result = self.db.fetch_one("""
                SELECT snapshot_id, folder_path, timestamp, url, title, metadata_json
                FROM snapshots
                WHERE request_id = ? AND url_id = ?
            """, (request_id, url_id))
            return result
        except Exception as e:
            logger.warning(f"Error checking for existing snapshot: {e}")
            return None

    def create_snapshot(
        self,
        url: str,
        request_id: str,
        files: Dict[str, IO],
        allow_existing: bool = False
    ) -> Snapshot:
        """
        Create new snapshot or add files to existing snapshot.

        Strategy:
        1. Check if snapshot with same request_id already exists for this URL
        2. If exists: add files to existing snapshot
        3. If not exists: create new snapshot with files
        4. Update database index accordingly

        Args:
            url: The URL being archived
            request_id: Unique request identifier (used for deduplication)
            files: Dictionary mapping artifact filenames to file streams
            allow_existing: If True, allow adding files to existing snapshot

        Returns:
            Snapshot object representing the created/updated snapshot

        Raises:
            ValidationError: If validation fails
            StorageError: If operation fails
        """
        try:
            # Parse URL
            domain, normalized_domain, normalized_path = parse_url(url)
            logger.debug(f"Parsed URL: domain={domain}, path={normalized_path}")

            # Build url_id for database lookup
            url_id = f"{normalized_domain}_{normalized_path}"

            # Check if snapshot already exists for this request_id
            existing_snapshot = self._find_existing_snapshot(request_id, url_id)

            if existing_snapshot:
                if not allow_existing:
                    raise StorageError(f"Snapshot already exists for request_id '{request_id}'")

                # Use existing snapshot - add files to it
                snapshot_id = existing_snapshot['snapshot_id']
                storage_path = Path(existing_snapshot['folder_path'])
                timestamp = datetime.fromisoformat(existing_snapshot['timestamp'])

                logger.info(
                    f"Found existing snapshot for request_id='{request_id}', "
                    f"adding files to snapshot_id={snapshot_id}"
                )

                # Store files in existing directory (always allow since snapshot exists)
                uploaded_artifacts = store_snapshot_files(
                    storage_path,
                    files,
                    self.validation_config,
                    allow_existing=True  # Always allow since we found existing snapshot
                )

                if uploaded_artifacts:
                    logger.info(
                        f"Added {len(uploaded_artifacts)} new artifacts to existing snapshot {snapshot_id}: "
                        f"{', '.join(uploaded_artifacts)}"
                    )
                else:
                    logger.info(f"No new artifacts to add to snapshot {snapshot_id} (all already exist)")

                # Parse metadata (may have been updated)
                metadata = {}
                metadata_path = storage_path / 'metadata.json'
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text())
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata.json for {snapshot_id}")

                # Get all artifacts for this snapshot (existing + new)
                artifact_rows = self.db.fetch_all("""
                    SELECT artifact_type FROM artifacts WHERE snapshot_id = ?
                """, (snapshot_id,))
                existing_artifacts = [row['artifact_type'] for row in artifact_rows]
                all_artifacts = list(set(existing_artifacts + uploaded_artifacts))

                # Create Snapshot object with all artifacts
                snapshot = Snapshot(
                    snapshot_id=snapshot_id,
                    timestamp=timestamp,
                    url=url,
                    title=metadata.get('title', existing_snapshot.get('title', '')),
                    folder_path=str(storage_path),
                    metadata=metadata,
                    available_artifacts=all_artifacts
                )

                # Update database with new artifacts only
                if uploaded_artifacts:
                    indexer = FilesystemIndexer(self.db, None)
                    indexer.add_artifacts_to_snapshot(snapshot, uploaded_artifacts)

                logger.info(f"Updated existing snapshot: {snapshot.snapshot_id}")
                return snapshot

            else:
                # Create new snapshot
                snapshot_id = generate_request_id(request_id)
                timestamp = datetime.now()

                # Build storage path
                # Format: {storage_path}/{domain}/{path}/{snapshot_id}
                storage_path = self.storage_path / normalized_domain / normalized_path / snapshot_id

                logger.info(
                    f"Creating new snapshot for URL '{url}' "
                    f"(request_id={request_id}, snapshot_id={snapshot_id})"
                )

                # Store files
                uploaded_artifacts = store_snapshot_files(
                    storage_path,
                    files,
                    self.validation_config,
                    allow_existing=allow_existing
                )

                logger.info(
                    f"Successfully stored snapshot {snapshot_id} "
                    f"with {len(uploaded_artifacts)} artifacts: {', '.join(uploaded_artifacts)}"
                )

                # Parse metadata if provided
                metadata = {}
                metadata_path = storage_path / 'metadata.json'
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text())
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata.json for {snapshot_id}")

                # Create Snapshot object
                snapshot = Snapshot(
                    snapshot_id=snapshot_id,
                    timestamp=timestamp,
                    url=url,
                    title=metadata.get('title', ''),
                    folder_path=str(storage_path),
                    metadata=metadata,
                    available_artifacts=uploaded_artifacts
                )

                # Index new snapshot with request_id for future lookups
                indexer = FilesystemIndexer(self.db, None)
                indexer.index_new_snapshot(snapshot, url_id, request_id=request_id)

                logger.info(f"Created and indexed new snapshot: {snapshot.snapshot_id}")
                return snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise StorageError(f"Snapshot creation failed: {str(e)}") from e

    def _get_snapshots_for_url(self, url_id: str) -> list[Snapshot]:
        """
        Get all snapshots for a URL.

        Uses 2 queries instead of 1+M (one per snapshot for artifacts).

        Args:
            url_id: The URL identifier

        Returns:
            List of Snapshot objects
        """
        # Query 1: All snapshots for this URL
        snapshot_rows = self.db.fetch_all("""
            SELECT snapshot_id, timestamp, url, title, folder_path,
                   status_code, content_type, content_length, metadata_json
            FROM snapshots
            WHERE url_id = ?
            ORDER BY timestamp DESC
        """, (url_id,))

        if not snapshot_rows:
            return []

        # Query 2: All artifacts for these snapshots in one batch
        snapshot_ids = [row['snapshot_id'] for row in snapshot_rows]
        placeholders = ','.join('?' * len(snapshot_ids))
        artifact_rows = self.db.fetch_all(f"""
            SELECT snapshot_id, artifact_type
            FROM artifacts
            WHERE snapshot_id IN ({placeholders})
        """, snapshot_ids)

        # Build lookup: snapshot_id -> [artifact_types]
        artifacts_by_snapshot = {}
        for row in artifact_rows:
            artifacts_by_snapshot.setdefault(row['snapshot_id'], []).append(row['artifact_type'])

        snapshots = []
        for snap_row in snapshot_rows:
            # Parse metadata
            metadata = {}
            if snap_row['metadata_json']:
                try:
                    metadata = json.loads(snap_row['metadata_json'])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for {snap_row['snapshot_id']}")

            snapshot = Snapshot(
                snapshot_id=snap_row['snapshot_id'],
                timestamp=datetime.fromisoformat(snap_row['timestamp']),
                url=snap_row['url'],
                title=snap_row['title'],
                folder_path=snap_row['folder_path'],
                metadata=metadata,
                available_artifacts=artifacts_by_snapshot.get(snap_row['snapshot_id'], [])
            )
            snapshots.append(snapshot)

        return snapshots
