"""
Tests for FilesystemIndexer - Indexes filesystem archives into SQLite.

Following TDD approach: Write tests first, then implement.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from io import BytesIO

from app.database.sqlite_manager import SQLiteManager
from app.database.models import get_schema_sql
from app.database.indexer import FilesystemIndexer
from app.storage.providers.filesystem import FilesystemStorageProvider
from configs.models import ValidationConfig
from app.models.snapshot import Snapshot
from app.models.url import ArchivedUrl


@pytest.fixture
def temp_storage_path(tmp_path):
    """Create temporary storage directory."""
    storage_path = tmp_path / "archives"
    storage_path.mkdir(parents=True)
    return storage_path


@pytest.fixture
def db_manager(tmp_path):
    """Provide SQLiteManager with initialized schema."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(db_path)
    manager.connect()
    manager.initialize_schema(get_schema_sql())
    yield manager
    manager.close()


@pytest.fixture
def fs_provider(temp_storage_path):
    """Provide FilesystemStorageProvider."""
    validation_config = ValidationConfig()
    return FilesystemStorageProvider(
        temp_storage_path,
        validation_config=validation_config
    )


@pytest.fixture
def indexer(db_manager, fs_provider):
    """Provide FilesystemIndexer."""
    return FilesystemIndexer(db_manager, fs_provider)


@pytest.fixture
def sample_snapshot_files(temp_storage_path):
    """Create sample snapshot files in filesystem."""
    # Create directory structure: domain/path/snapshot_id/
    snapshot_dir = temp_storage_path / "example_com" / "home" / "req_test_20240101_120000"
    snapshot_dir.mkdir(parents=True)

    # Create metadata.json
    metadata = {
        "url": "https://example.com/home",
        "title": "Example Home",
        "status": 200,
        "content_type": "text/html",
        "content_length": 1024,
        "timestamp": "2024-01-01T12:00:00Z"
    }
    (snapshot_dir / "metadata.json").write_text(json.dumps(metadata))

    # Create artifact files
    (snapshot_dir / "archive.wacz").write_bytes(b"fake wacz content")
    (snapshot_dir / "screenshot.png").write_bytes(b"fake png content")

    return snapshot_dir


class TestFilesystemIndexerInitialization:
    """Test indexer initialization."""

    def test_indexer_initialization(self, db_manager, fs_provider):
        """Test that indexer initializes correctly."""
        indexer = FilesystemIndexer(db_manager, fs_provider)

        assert indexer.db == db_manager
        assert indexer.fs_provider == fs_provider


class TestIndexSingleSnapshot:
    """Test indexing single snapshot."""

    def test_index_snapshot_inserts_url_record(self, indexer, db_manager):
        """Test that indexing snapshot creates URL record."""
        snapshot = Snapshot(
            snapshot_id="req_test_20240101_120000",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            url="https://example.com/home",
            title="Example Home",
            folder_path="/path/to/snapshot",
            metadata={"status": 200},
            available_artifacts=["archive.wacz"]
        )

        indexer.index_new_snapshot(snapshot, "example_com_home")

        # Verify URL record exists
        url_record = db_manager.fetch_one(
            "SELECT * FROM urls WHERE url_id = ?",
            ("example_com_home",)
        )
        assert url_record is not None
        assert url_record['url_id'] == "example_com_home"
        assert url_record['original_url'] == "https://example.com/home"

    def test_index_snapshot_inserts_snapshot_record(self, indexer, db_manager):
        """Test that indexing snapshot creates snapshot record."""
        snapshot = Snapshot(
            snapshot_id="req_test_20240101_120000",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            url="https://example.com/home",
            title="Example Home",
            folder_path="/path/to/snapshot",
            metadata={"status": 200, "content_type": "text/html"},
            available_artifacts=["archive.wacz"]
        )

        indexer.index_new_snapshot(snapshot, "example_com_home")

        # Verify snapshot record exists
        snapshot_record = db_manager.fetch_one(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            ("req_test_20240101_120000",)
        )
        assert snapshot_record is not None
        assert snapshot_record['snapshot_id'] == "req_test_20240101_120000"
        assert snapshot_record['url_id'] == "example_com_home"
        assert snapshot_record['title'] == "Example Home"
        assert snapshot_record['status_code'] == 200

    def test_index_snapshot_inserts_artifact_records(self, indexer, db_manager):
        """Test that indexing snapshot creates artifact records."""
        snapshot = Snapshot(
            snapshot_id="req_test_20240101_120000",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            url="https://example.com/home",
            title="Example Home",
            folder_path="/path/to/snapshot",
            metadata={},
            available_artifacts=["archive.wacz", "screenshot.png"]
        )

        indexer.index_new_snapshot(snapshot, "example_com_home")

        # Verify artifact records exist
        artifacts = db_manager.fetch_all(
            "SELECT * FROM artifacts WHERE snapshot_id = ?",
            ("req_test_20240101_120000",)
        )
        assert len(artifacts) == 2
        artifact_types = [a['artifact_type'] for a in artifacts]
        assert "archive.wacz" in artifact_types
        assert "screenshot.png" in artifact_types

    def test_index_snapshot_updates_existing_url(self, indexer, db_manager):
        """Test that indexing second snapshot updates URL record."""
        # Index first snapshot
        snapshot1 = Snapshot(
            snapshot_id="req_test_20240101_120000",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            url="https://example.com/home",
            title="Example Home",
            folder_path="/path/to/snapshot1",
            metadata={},
            available_artifacts=[]
        )
        indexer.index_new_snapshot(snapshot1, "example_com_home")

        # Index second snapshot for same URL
        snapshot2 = Snapshot(
            snapshot_id="req_test_20240102_120000",
            timestamp=datetime(2024, 1, 2, 12, 0, 0),
            url="https://example.com/home",
            title="Example Home Updated",
            folder_path="/path/to/snapshot2",
            metadata={},
            available_artifacts=[]
        )
        indexer.index_new_snapshot(snapshot2, "example_com_home")

        # Verify URL record updated
        url_record = db_manager.fetch_one(
            "SELECT * FROM urls WHERE url_id = ?",
            ("example_com_home",)
        )
        assert url_record['snapshot_count'] == 2
        assert url_record['last_captured'] == "2024-01-02T12:00:00"


class TestRebuildIndex:
    """Test full index rebuild."""

    def test_rebuild_index_clears_existing_data(self, indexer, db_manager):
        """Test that rebuild clears existing database data."""
        # Insert some existing data
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ("old_url", "https://old.com", "old_url", 1))

        # Rebuild index (will be empty since no files in filesystem)
        stats = indexer.rebuild_index()

        # Verify old data is cleared
        url_record = db_manager.fetch_one(
            "SELECT * FROM urls WHERE url_id = ?",
            ("old_url",)
        )
        assert url_record is None
        assert stats['urls'] == 0

    def test_rebuild_index_indexes_all_urls(self, indexer, db_manager, sample_snapshot_files):
        """Test that rebuild indexes all URLs from filesystem."""
        stats = indexer.rebuild_index()

        # Verify URL was indexed
        assert stats['urls'] >= 1
        url_record = db_manager.fetch_one(
            "SELECT * FROM urls WHERE url_id = ?",
            ("example_com_home",)
        )
        assert url_record is not None

    def test_rebuild_index_indexes_all_snapshots(self, indexer, db_manager, sample_snapshot_files):
        """Test that rebuild indexes all snapshots."""
        stats = indexer.rebuild_index()

        # Verify snapshot was indexed
        assert stats['snapshots'] >= 1
        snapshot_record = db_manager.fetch_one(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            ("req_test_20240101_120000",)
        )
        assert snapshot_record is not None

    def test_rebuild_index_indexes_all_artifacts(self, indexer, db_manager, sample_snapshot_files):
        """Test that rebuild indexes all artifacts."""
        stats = indexer.rebuild_index()

        # Verify artifacts were indexed
        assert stats['artifacts'] >= 2  # wacz and screenshot
        artifacts = db_manager.fetch_all(
            "SELECT * FROM artifacts WHERE snapshot_id = ?",
            ("req_test_20240101_120000",)
        )
        assert len(artifacts) >= 2

    def test_rebuild_index_returns_statistics(self, indexer):
        """Test that rebuild returns statistics dict."""
        stats = indexer.rebuild_index()

        assert isinstance(stats, dict)
        assert 'urls' in stats
        assert 'snapshots' in stats
        assert 'artifacts' in stats
        assert 'errors' in stats
        assert all(isinstance(v, int) for v in stats.values())

    def test_rebuild_index_with_progress_callback(self, indexer, sample_snapshot_files):
        """Test that rebuild calls progress callback."""
        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        stats = indexer.rebuild_index(progress_callback=progress_callback)

        # Verify callback was called
        assert len(progress_calls) > 0
        # First call should have current >= 1, total >= 1
        current, total, message = progress_calls[0]
        assert current >= 1
        assert total >= 1
        assert isinstance(message, str)


class TestIndexURL:
    """Test indexing complete URL with snapshots."""

    def test_index_url_with_multiple_snapshots(self, indexer, db_manager):
        """Test indexing ArchivedUrl with multiple snapshots."""
        snapshots = [
            Snapshot(
                snapshot_id="req_test_20240101_120000",
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                url="https://example.com/home",
                title="Snapshot 1",
                folder_path="/path/1",
                metadata={},
                available_artifacts=["archive.wacz"]
            ),
            Snapshot(
                snapshot_id="req_test_20240102_120000",
                timestamp=datetime(2024, 1, 2, 12, 0, 0),
                url="https://example.com/home",
                title="Snapshot 2",
                folder_path="/path/2",
                metadata={},
                available_artifacts=["screenshot.png"]
            )
        ]

        archived_url = ArchivedUrl(
            url_id="example_com_home",
            original_url="https://example.com/home",
            folder_name="example_com/home",
            snapshots=snapshots
        )

        indexer._index_url(archived_url)

        # Verify URL record
        url_record = db_manager.fetch_one(
            "SELECT * FROM urls WHERE url_id = ?",
            ("example_com_home",)
        )
        assert url_record is not None
        assert url_record['snapshot_count'] == 2

        # Verify both snapshots indexed
        snapshot_records = db_manager.fetch_all(
            "SELECT * FROM snapshots WHERE url_id = ?",
            ("example_com_home",)
        )
        assert len(snapshot_records) == 2


class TestErrorHandling:
    """Test error handling in indexer."""

    def test_index_snapshot_handles_missing_metadata(self, indexer, db_manager):
        """Test indexing snapshot with minimal metadata."""
        snapshot = Snapshot(
            snapshot_id="req_test_20240101_120000",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            url="https://example.com",
            title=None,
            folder_path="/path",
            metadata={},
            available_artifacts=[]
        )

        # Should not raise error
        indexer.index_new_snapshot(snapshot, "example_com")

        snapshot_record = db_manager.fetch_one(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            ("req_test_20240101_120000",)
        )
        assert snapshot_record is not None
        assert snapshot_record['title'] is None

    def test_rebuild_index_continues_on_errors(self, indexer, db_manager, temp_storage_path):
        """Test that rebuild continues even if some URLs fail."""
        # Create invalid snapshot directory (no metadata)
        invalid_dir = temp_storage_path / "invalid_com" / "test" / "req_bad_20240101_120000"
        invalid_dir.mkdir(parents=True)

        # Should complete without raising
        stats = indexer.rebuild_index()

        # May have errors but should complete
        assert isinstance(stats, dict)
        assert 'errors' in stats
