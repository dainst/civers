"""
Tests for FilesystemStorageProvider.create_snapshot() method.

Tests the snapshot creation functionality including file storage,
idempotent operations, error handling, and integration with URL parsing.
"""

import pytest
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

from app.storage.providers.filesystem import FilesystemStorageProvider
from configs.models import ValidationConfig
from app.custom_exceptions.exceptions.api_exceptions import ValidationError
from app.storage.providers.storage_provider_interface import StorageError


@pytest.fixture
def validation_config():
    """Provide validation configuration."""
    return ValidationConfig()


@pytest.fixture
def temp_storage_path(tmp_path):
    """Provide temporary storage directory."""
    storage_path = tmp_path / "archives"
    storage_path.mkdir()
    return storage_path


@pytest.fixture
def filesystem_provider(temp_storage_path, validation_config):
    """Provide FilesystemStorageProvider instance."""
    return FilesystemStorageProvider(
        storage_path=temp_storage_path,
        timeout_seconds=10,
        validation_config=validation_config
    )


class TestCreateSnapshotBasic:
    """Basic snapshot creation tests."""

    def test_create_snapshot_with_single_file(self, filesystem_provider, temp_storage_path):
        """Test creating snapshot with a single file."""
        files = {
            'archive.wacz': BytesIO(b'wacz content')
        }

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test1',
            files=files
        )

        # Verify snapshot object
        assert snapshot.snapshot_id.startswith('req_test1_')
        assert str(snapshot.url) == 'https://example.com/page'
        assert 'archive.wacz' in snapshot.available_artifacts
        assert len(snapshot.available_artifacts) == 1

        # Verify files on disk
        snapshot_path = Path(snapshot.folder_path)
        assert snapshot_path.exists()
        assert (snapshot_path / 'archive.wacz').exists()
        assert (snapshot_path / 'archive.wacz').read_bytes() == b'wacz content'

    def test_create_snapshot_with_multiple_files(self, filesystem_provider, temp_storage_path):
        """Test creating snapshot with multiple files."""
        metadata = {'url': 'https://example.com', 'title': 'Example'}
        files = {
            'archive.wacz': BytesIO(b'wacz content'),
            'screenshot.png': BytesIO(b'png content'),
            'metadata.json': BytesIO(json.dumps(metadata).encode('utf-8'))
        }

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/about',
            request_id='test2',
            files=files
        )

        # Verify all files created
        assert len(snapshot.available_artifacts) == 3
        assert 'archive.wacz' in snapshot.available_artifacts
        assert 'screenshot.png' in snapshot.available_artifacts
        assert 'metadata.json' in snapshot.available_artifacts

        # Verify directory structure
        snapshot_path = Path(snapshot.folder_path)
        assert 'example_com' in str(snapshot_path)
        assert 'about' in str(snapshot_path)

        # Verify metadata parsing
        assert snapshot.title == 'Example'

    def test_create_snapshot_url_normalization(self, filesystem_provider, temp_storage_path):
        """Test that URLs are properly normalized in directory structure."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/about-us',
            request_id='test3',
            files=files
        )

        snapshot_path = Path(snapshot.folder_path)
        # Path should be normalized: about-us -> about_us
        assert 'example_com' in str(snapshot_path)
        assert 'about_us' in str(snapshot_path)

    def test_create_snapshot_generates_unique_ids(self, filesystem_provider, temp_storage_path):
        """Test that different snapshots get unique IDs."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot1 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test4',
            files=files
        )

        # Create another snapshot with same URL but different request_id
        snapshot2 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test5',
            files=files
        )

        assert snapshot1.snapshot_id != snapshot2.snapshot_id
        assert snapshot1.folder_path != snapshot2.folder_path


class TestIdempotentOperations:
    """Tests for idempotent snapshot operations."""

    def test_same_request_id_reuses_existing_snapshot(self, filesystem_provider, temp_storage_path):
        """Test that same request_id + URL reuses existing snapshot automatically."""
        files1 = {'archive.wacz': BytesIO(b'content')}

        # First creation should succeed
        snapshot1 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test6',
            files=files1
        )

        # Second creation with same request_id should add to existing snapshot (not fail)
        files2 = {'screenshot.png': BytesIO(b'screenshot content')}
        snapshot2 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test6',
            files=files2
        )

        # Should use the same snapshot_id (same directory)
        assert snapshot1.snapshot_id == snapshot2.snapshot_id
        assert snapshot1.folder_path == snapshot2.folder_path
        
        # Second snapshot should have both artifacts
        assert len(snapshot2.available_artifacts) == 2
        assert 'archive.wacz' in snapshot2.available_artifacts
        assert 'screenshot.png' in snapshot2.available_artifacts

    def test_add_files_to_existing_snapshot(self, filesystem_provider, temp_storage_path):
        """Test adding files to existing snapshot with same request_id."""
        # First upload - create snapshot with archive.wacz
        files1 = {'archive.wacz': BytesIO(b'wacz content')}
        snapshot1 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test7',
            files=files1
        )

        assert len(snapshot1.available_artifacts) == 1
        assert 'archive.wacz' in snapshot1.available_artifacts

        # Second upload - add screenshot to existing snapshot
        files2 = {'screenshot.png': BytesIO(b'png content')}
        snapshot2 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test7',
            files=files2,
            allow_existing=True
        )

        # Should list ALL artifacts in the snapshot (existing + new)
        assert len(snapshot2.available_artifacts) == 2
        assert 'archive.wacz' in snapshot2.available_artifacts
        assert 'screenshot.png' in snapshot2.available_artifacts

        # Should use the same snapshot directory
        assert snapshot1.snapshot_id == snapshot2.snapshot_id
        assert snapshot1.folder_path == snapshot2.folder_path

        # Verify both files exist on disk
        snapshot_path = Path(snapshot2.folder_path)
        assert (snapshot_path / 'archive.wacz').exists()
        assert (snapshot_path / 'screenshot.png').exists()

    def test_existing_files_not_overwritten(self, filesystem_provider, temp_storage_path):
        """Test that existing files are not overwritten when adding to snapshot."""
        # First upload
        original_content = b'original wacz content'
        files1 = {'archive.wacz': BytesIO(original_content)}
        snapshot1 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test8',
            files=files1
        )

        # Second upload with same filename but different content
        new_content = b'new wacz content - should not overwrite'
        files2 = {'archive.wacz': BytesIO(new_content)}
        snapshot2 = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test8',
            files=files2,
            allow_existing=True
        )

        # available_artifacts should still include archive.wacz (it exists)
        assert 'archive.wacz' in snapshot2.available_artifacts

        # Original content should be preserved (not overwritten)
        snapshot_path = Path(snapshot2.folder_path)
        saved_content = (snapshot_path / 'archive.wacz').read_bytes()
        assert saved_content == original_content


class TestErrorHandling:
    """Tests for error handling in create_snapshot."""

    def test_invalid_url_raises_error(self, filesystem_provider, temp_storage_path):
        """Test that invalid URL raises appropriate error."""
        files = {'archive.wacz': BytesIO(b'content')}

        with pytest.raises(Exception):  # URL parser should raise an error
            filesystem_provider.create_snapshot(
                url='not-a-valid-url',
                request_id='test9',
                files=files
            )

    def test_invalid_artifact_type_raises_error(self, filesystem_provider, temp_storage_path):
        """Test that invalid artifact type raises ValidationError."""
        files = {'malware.exe': BytesIO(b'bad content')}

        with pytest.raises(ValidationError, match="Invalid artifact type"):
            filesystem_provider.create_snapshot(
                url='https://example.com/page',
                request_id='test10',
                files=files
            )

    def test_empty_files_creates_empty_snapshot(self, filesystem_provider, temp_storage_path):
        """Test that creating snapshot with no files creates empty directory."""
        files = {}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test11',
            files=files
        )

        assert len(snapshot.available_artifacts) == 0
        assert Path(snapshot.folder_path).exists()


class TestCacheInvalidation:
    """Tests for cache invalidation after snapshot creation."""

    def test_new_snapshot_visible_after_create(self, filesystem_provider, temp_storage_path):
        """Test that newly created snapshot is visible in subsequent reads."""
        # Get initial state
        initial_urls = filesystem_provider.get_all_urls()
        initial_count = len(initial_urls)

        # Create new snapshot
        files = {'archive.wacz': BytesIO(b'content')}
        filesystem_provider.create_snapshot(
            url='https://newsite.com/page',
            request_id='test12',
            files=files
        )

        # Fresh read should include the new snapshot
        updated_urls = filesystem_provider.get_all_urls()
        assert len(updated_urls) == initial_count + 1


class TestMetadataParsing:
    """Tests for metadata parsing in created snapshots."""

    def test_metadata_json_parsed(self, filesystem_provider, temp_storage_path):
        """Test that metadata.json is parsed and included in snapshot."""
        metadata = {
            'url': 'https://example.com/page',
            'title': 'Example Page Title',
            'timestamp': '2025-01-11T12:00:00'
        }
        files = {
            'archive.wacz': BytesIO(b'content'),
            'metadata.json': BytesIO(json.dumps(metadata).encode('utf-8'))
        }

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test13',
            files=files
        )

        # Verify metadata was parsed
        assert snapshot.title == 'Example Page Title'
        assert snapshot.metadata['timestamp'] == '2025-01-11T12:00:00'

    def test_snapshot_without_metadata(self, filesystem_provider, temp_storage_path):
        """Test snapshot creation without metadata.json."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test14',
            files=files
        )

        # Should have empty title and metadata
        assert snapshot.title == ''
        assert snapshot.metadata == {}


class TestDirectoryStructure:
    """Tests for proper directory structure creation."""

    def test_three_level_hierarchy(self, filesystem_provider, temp_storage_path):
        """Test that proper three-level hierarchy is created."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/about/team',
            request_id='test15',
            files=files
        )

        snapshot_path = Path(snapshot.folder_path)

        # Verify path structure: storage_path / domain / path / snapshot_id
        parts = snapshot_path.relative_to(temp_storage_path).parts
        assert len(parts) == 3
        assert parts[0] == 'example_com'  # domain
        assert parts[1] == 'about_team'  # path
        assert parts[2].startswith('req_test15_')  # snapshot_id

    def test_parent_directories_created(self, filesystem_provider, temp_storage_path):
        """Test that parent directories are created automatically."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://newdomain.org/deep/nested/path',
            request_id='test16',
            files=files
        )

        snapshot_path = Path(snapshot.folder_path)
        assert snapshot_path.exists()
        assert snapshot_path.parent.exists()  # path directory
        assert snapshot_path.parent.parent.exists()  # domain directory


class TestTimestampHandling:
    """Tests for timestamp generation and parsing."""

    def test_timestamp_in_snapshot_id(self, filesystem_provider, temp_storage_path):
        """Test that snapshot ID includes timestamp."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test17',
            files=files
        )

        # Snapshot ID should match format: req_{request_id}_{YYYYMMDD_HHMMSS}
        assert snapshot.snapshot_id.startswith('req_test17_')
        parts = snapshot.snapshot_id.split('_')
        assert len(parts) >= 3

        # Last two parts should be date and time
        date_part = parts[-2]
        time_part = parts[-1]
        assert len(date_part) == 8  # YYYYMMDD
        assert len(time_part) == 6  # HHMMSS

    def test_timestamp_parsed_from_snapshot_id(self, filesystem_provider, temp_storage_path):
        """Test that timestamp is parsed from snapshot ID."""
        from datetime import timedelta

        files = {'archive.wacz': BytesIO(b'content')}

        snapshot = filesystem_provider.create_snapshot(
            url='https://example.com/page',
            request_id='test18',
            files=files
        )

        # Timestamp should be datetime object
        assert isinstance(snapshot.timestamp, datetime)
        # Should be recent (within last minute)
        assert snapshot.timestamp > datetime.now() - timedelta(minutes=1)
