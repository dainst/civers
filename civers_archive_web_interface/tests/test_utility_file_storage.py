"""
Tests for file storage utilities.

Tests atomic file writes, directory creation, and the complete snapshot storage workflow.
Note: metadata.json is now uploaded as a regular file, not generated automatically.
"""

import pytest
import json
from io import BytesIO
from pathlib import Path
from app.utils.file_storage import (
    validate_artifact_type,
    create_storage_directory,
    write_file_atomic,
    cleanup_directory,
    store_snapshot_files
)
from configs.models import ValidationConfig
from app.custom_exceptions.exceptions.api_exceptions import ValidationError
from app.storage.providers.storage_provider_interface import StorageError


@pytest.fixture
def validation_config():
    """Provide validation configuration."""
    return ValidationConfig()


@pytest.fixture
def temp_storage(tmp_path):
    """Provide temporary storage directory."""
    storage_dir = tmp_path / "test_storage"
    return storage_dir


class TestValidateArtifactType:
    """Tests for validate_artifact_type function."""

    def test_valid_artifact_wacz(self, validation_config):
        """Test validation of valid WACZ artifact."""
        # Should not raise
        validate_artifact_type('archive.wacz', validation_config)

    def test_valid_artifact_screenshot(self, validation_config):
        """Test validation of valid screenshot artifact."""
        validate_artifact_type('screenshot.png', validation_config)

    def test_valid_artifact_singlefile(self, validation_config):
        """Test validation of valid SingleFile artifact."""
        validate_artifact_type('singlefile.html', validation_config)

    def test_valid_artifact_metadata(self, validation_config):
        """Test validation of valid metadata artifact."""
        validate_artifact_type('metadata.json', validation_config)

    def test_invalid_artifact_type(self, validation_config):
        """Test that invalid artifact type raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid artifact type"):
            validate_artifact_type('malware.exe', validation_config)

    def test_invalid_artifact_script(self, validation_config):
        """Test that script files are rejected."""
        with pytest.raises(ValidationError, match="Invalid artifact type"):
            validate_artifact_type('script.js', validation_config)

    def test_error_message_includes_allowed_types(self, validation_config):
        """Test that error message lists allowed types."""
        with pytest.raises(ValidationError) as exc_info:
            validate_artifact_type('invalid.txt', validation_config)

        error_msg = str(exc_info.value)
        assert "Allowed types:" in error_msg
        assert "archive.wacz" in error_msg


class TestCreateStorageDirectory:
    """Tests for create_storage_directory function."""

    def test_create_new_directory(self, temp_storage):
        """Test creating a new directory."""
        snapshot_dir = temp_storage / "snapshot1"
        created = create_storage_directory(snapshot_dir)

        assert created is True
        assert snapshot_dir.exists()
        assert snapshot_dir.is_dir()

    def test_create_with_parents(self, temp_storage):
        """Test creating directory with parent directories."""
        snapshot_dir = temp_storage / "domain" / "path" / "snapshot1"
        created = create_storage_directory(snapshot_dir)

        assert created is True
        assert snapshot_dir.exists()
        assert snapshot_dir.parent.exists()

    def test_duplicate_directory_raises_error(self, temp_storage):
        """Test that creating duplicate directory raises ValidationError."""
        snapshot_dir = temp_storage / "snapshot1"
        create_storage_directory(snapshot_dir)

        with pytest.raises(ValidationError, match="Snapshot already exists"):
            create_storage_directory(snapshot_dir)

    def test_error_message_includes_snapshot_name(self, temp_storage):
        """Test that error message includes snapshot name."""
        snapshot_dir = temp_storage / "req_123_20250111_120000"
        create_storage_directory(snapshot_dir)

        with pytest.raises(ValidationError) as exc_info:
            create_storage_directory(snapshot_dir)

        assert "req_123_20250111_120000" in str(exc_info.value)

    def test_allow_existing_directory(self, temp_storage):
        """Test that allow_existing=True allows existing directories."""
        snapshot_dir = temp_storage / "snapshot1"
        created1 = create_storage_directory(snapshot_dir)
        assert created1 is True

        # Should not raise, should return False
        created2 = create_storage_directory(snapshot_dir, allow_existing=True)
        assert created2 is False


class TestWriteFileAtomic:
    """Tests for write_file_atomic function."""

    def test_write_valid_file(self, temp_storage, validation_config):
        """Test writing a valid file atomically."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'archive.wacz'
        content = BytesIO(b'test wacz content')

        written = write_file_atomic(file_path, content, validation_config)

        assert written is True
        assert file_path.exists()
        assert file_path.read_bytes() == b'test wacz content'

    def test_temp_file_removed_after_success(self, temp_storage, validation_config):
        """Test that temporary file is removed after successful write."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'screenshot.png'
        temp_path = file_path.with_suffix('.png.tmp')
        content = BytesIO(b'png content')

        write_file_atomic(file_path, content, validation_config)

        assert not temp_path.exists()

    def test_invalid_artifact_type(self, temp_storage, validation_config):
        """Test that invalid artifact type raises ValidationError."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'malware.exe'
        content = BytesIO(b'bad content')

        with pytest.raises(ValidationError, match="Invalid artifact type"):
            write_file_atomic(file_path, content, validation_config)

    def test_temp_file_cleaned_up_on_error(self, temp_storage, validation_config):
        """Test that temp file is cleaned up if write fails."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'malware.exe'
        temp_path = file_path.with_suffix('.exe.tmp')
        content = BytesIO(b'bad content')

        with pytest.raises(ValidationError):
            write_file_atomic(file_path, content, validation_config)

        assert not temp_path.exists()

    def test_large_file_write(self, temp_storage, validation_config):
        """Test writing a large file."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'archive.wacz'
        large_content = b'x' * (10 * 1024 * 1024)  # 10MB
        content = BytesIO(large_content)

        write_file_atomic(file_path, content, validation_config)

        assert file_path.stat().st_size == 10 * 1024 * 1024

    def test_skip_if_exists(self, temp_storage, validation_config):
        """Test that skip_if_exists=True skips existing files."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)

        file_path = snapshot_dir / 'archive.wacz'
        original_content = b'original content'
        new_content = b'new content'

        # Write original
        written1 = write_file_atomic(file_path, BytesIO(original_content), validation_config)
        assert written1 is True

        # Try to write again with skip_if_exists=True
        written2 = write_file_atomic(file_path, BytesIO(new_content), validation_config, skip_if_exists=True)
        assert written2 is False

        # Content should remain original
        assert file_path.read_bytes() == original_content


class TestCleanupDirectory:
    """Tests for cleanup_directory function."""

    def test_cleanup_existing_directory(self, temp_storage):
        """Test cleaning up an existing directory."""
        snapshot_dir = temp_storage / "snapshot1"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "test.txt").write_text("test")

        cleanup_directory(snapshot_dir)

        assert not snapshot_dir.exists()

    def test_cleanup_nonexistent_directory(self, temp_storage):
        """Test that cleaning up nonexistent directory doesn't raise error."""
        snapshot_dir = temp_storage / "nonexistent"

        # Should not raise
        cleanup_directory(snapshot_dir)

    def test_cleanup_nested_directories(self, temp_storage):
        """Test cleaning up directory with nested structure."""
        snapshot_dir = temp_storage / "snapshot1"
        (snapshot_dir / "subdir" / "nested").mkdir(parents=True)
        (snapshot_dir / "file1.txt").write_text("test1")
        (snapshot_dir / "subdir" / "file2.txt").write_text("test2")

        cleanup_directory(snapshot_dir)

        assert not snapshot_dir.exists()

    def test_cleanup_doesnt_affect_parent(self, temp_storage):
        """Test that cleanup doesn't affect parent directories."""
        parent_dir = temp_storage / "parent"
        snapshot_dir = parent_dir / "snapshot1"
        parent_dir.mkdir(parents=True)
        snapshot_dir.mkdir()

        cleanup_directory(snapshot_dir)

        assert not snapshot_dir.exists()
        assert parent_dir.exists()


class TestStoreSnapshotFiles:
    """Tests for store_snapshot_files function."""

    def test_store_complete_snapshot(self, temp_storage, validation_config):
        """Test storing a complete snapshot with all artifact types."""
        snapshot_dir = temp_storage / "snapshot1"

        metadata = {
            'url': 'https://example.com',
            'title': 'Example Page',
            'timestamp': '2025-01-11T12:00:00'
        }

        files = {
            'archive.wacz': BytesIO(b'wacz content'),
            'screenshot.png': BytesIO(b'png content'),
            'singlefile.html': BytesIO(b'html content'),
            'metadata.json': BytesIO(json.dumps(metadata).encode('utf-8'))
        }

        artifacts = store_snapshot_files(snapshot_dir, files, validation_config)

        # Verify directory created
        assert snapshot_dir.exists()

        # Verify all files written
        assert (snapshot_dir / 'archive.wacz').exists()
        assert (snapshot_dir / 'screenshot.png').exists()
        assert (snapshot_dir / 'singlefile.html').exists()
        assert (snapshot_dir / 'metadata.json').exists()

        # Verify artifacts list
        assert 'archive.wacz' in artifacts
        assert 'screenshot.png' in artifacts
        assert 'singlefile.html' in artifacts
        assert 'metadata.json' in artifacts
        assert len(artifacts) == 4

        # Verify metadata content
        saved_metadata = json.loads((snapshot_dir / 'metadata.json').read_text())
        assert saved_metadata['url'] == 'https://example.com'
        assert saved_metadata['title'] == 'Example Page'

    def test_store_minimal_snapshot(self, temp_storage, validation_config):
        """Test storing snapshot with minimal files."""
        snapshot_dir = temp_storage / "snapshot2"

        files = {
            'archive.wacz': BytesIO(b'wacz only')
        }

        artifacts = store_snapshot_files(snapshot_dir, files, validation_config)

        assert snapshot_dir.exists()
        assert (snapshot_dir / 'archive.wacz').exists()
        assert len(artifacts) == 1

    def test_store_cleanup_on_invalid_artifact(self, temp_storage, validation_config):
        """Test that directory is cleaned up if invalid artifact is provided."""
        snapshot_dir = temp_storage / "snapshot3"

        files = {
            'archive.wacz': BytesIO(b'valid content'),
            'malware.exe': BytesIO(b'invalid content')
        }

        with pytest.raises(ValidationError):
            store_snapshot_files(snapshot_dir, files, validation_config)

        # Directory should be cleaned up
        assert not snapshot_dir.exists()

    def test_store_cleanup_on_duplicate_directory(self, temp_storage, validation_config):
        """Test that error is raised if directory already exists."""
        snapshot_dir = temp_storage / "snapshot4"
        snapshot_dir.mkdir(parents=True)

        files = {'archive.wacz': BytesIO(b'content')}

        with pytest.raises(ValidationError, match="Snapshot already exists"):
            store_snapshot_files(snapshot_dir, files, validation_config)

    def test_file_content_preserved(self, temp_storage, validation_config):
        """Test that file content is correctly preserved."""
        snapshot_dir = temp_storage / "snapshot5"

        test_content = b'This is test WACZ content with special chars: \x00\x01\x02'
        files = {'archive.wacz': BytesIO(test_content)}

        store_snapshot_files(snapshot_dir, files, validation_config)

        # Verify content
        saved_content = (snapshot_dir / 'archive.wacz').read_bytes()
        assert saved_content == test_content


class TestIdempotentOperations:
    """Tests for idempotent operations (adding files to existing snapshots)."""

    def test_add_files_to_existing_snapshot(self, temp_storage, validation_config):
        """Test adding new files to an existing snapshot."""
        snapshot_dir = temp_storage / "snapshot1"

        # First upload - create snapshot with archive.wacz
        files1 = {'archive.wacz': BytesIO(b'wacz content')}
        artifacts1 = store_snapshot_files(snapshot_dir, files1, validation_config)

        assert 'archive.wacz' in artifacts1
        assert (snapshot_dir / 'archive.wacz').exists()

        # Second upload - add screenshot to existing snapshot
        files2 = {'screenshot.png': BytesIO(b'png content')}
        artifacts2 = store_snapshot_files(
            snapshot_dir,
            files2,
            validation_config,
            allow_existing=True
        )

        assert 'screenshot.png' in artifacts2
        assert 'archive.wacz' not in artifacts2  # Not re-uploaded
        assert (snapshot_dir / 'screenshot.png').exists()
        assert (snapshot_dir / 'archive.wacz').exists()

    def test_existing_files_not_overwritten(self, temp_storage, validation_config):
        """Test that existing files are not overwritten in idempotent mode."""
        snapshot_dir = temp_storage / "snapshot2"

        # First upload
        original_content = b'original wacz content'
        files1 = {'archive.wacz': BytesIO(original_content)}
        store_snapshot_files(snapshot_dir, files1, validation_config)

        # Second upload with same filename but different content
        new_content = b'new wacz content - should not overwrite'
        files2 = {'archive.wacz': BytesIO(new_content)}
        artifacts2 = store_snapshot_files(
            snapshot_dir,
            files2,
            validation_config,
            allow_existing=True
        )

        # File should not be in artifacts list (not written)
        assert 'archive.wacz' not in artifacts2

        # Original content should be preserved
        saved_content = (snapshot_dir / 'archive.wacz').read_bytes()
        assert saved_content == original_content

    def test_multiple_additions(self, temp_storage, validation_config):
        """Test multiple sequential additions to same snapshot."""
        snapshot_dir = temp_storage / "snapshot3"

        # First upload - archive
        files1 = {'archive.wacz': BytesIO(b'wacz')}
        store_snapshot_files(snapshot_dir, files1, validation_config)

        # Second upload - screenshot
        files2 = {'screenshot.png': BytesIO(b'png')}
        store_snapshot_files(
            snapshot_dir,
            files2,
            validation_config,
            allow_existing=True
        )

        # Third upload - singlefile
        files3 = {'singlefile.html': BytesIO(b'html')}
        store_snapshot_files(
            snapshot_dir,
            files3,
            validation_config,
            allow_existing=True
        )

        # All files should exist
        assert (snapshot_dir / 'archive.wacz').exists()
        assert (snapshot_dir / 'screenshot.png').exists()
        assert (snapshot_dir / 'singlefile.html').exists()

    def test_allow_existing_false_prevents_additions(self, temp_storage, validation_config):
        """Test that allow_existing=False prevents additions to existing snapshots."""
        snapshot_dir = temp_storage / "snapshot4"

        # First upload
        files1 = {'archive.wacz': BytesIO(b'wacz')}
        store_snapshot_files(snapshot_dir, files1, validation_config)

        # Second upload without allow_existing should fail
        files2 = {'screenshot.png': BytesIO(b'png')}
        with pytest.raises(ValidationError, match="Snapshot already exists"):
            store_snapshot_files(
                snapshot_dir,
                files2,
                validation_config,
                allow_existing=False  # Default
            )


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_files_dict(self, temp_storage, validation_config):
        """Test storing snapshot with empty files dict."""
        snapshot_dir = temp_storage / "snapshot1"

        files = {}

        artifacts = store_snapshot_files(snapshot_dir, files, validation_config)

        assert snapshot_dir.exists()
        assert len(artifacts) == 0

    def test_concurrent_directory_creation(self, temp_storage, validation_config):
        """Test handling of concurrent directory creation."""
        snapshot_dir = temp_storage / "snapshot2"

        # Create directory manually (simulating concurrent creation)
        snapshot_dir.mkdir(parents=True)

        files = {'archive.wacz': BytesIO(b'content')}

        # Should raise ValidationError by default
        with pytest.raises(ValidationError, match="Snapshot already exists"):
            store_snapshot_files(snapshot_dir, files, validation_config)

        # But should work with allow_existing=True
        artifacts = store_snapshot_files(
            snapshot_dir,
            files,
            validation_config,
            allow_existing=True
        )
        assert 'archive.wacz' in artifacts

    def test_very_large_metadata(self, temp_storage, validation_config):
        """Test storing snapshot with large metadata file."""
        snapshot_dir = temp_storage / "snapshot3"

        # Create large metadata
        large_metadata = {
            'url': 'https://example.com',
            'data': 'x' * (1024 * 1024)  # 1MB of data
        }

        files = {
            'archive.wacz': BytesIO(b'content'),
            'metadata.json': BytesIO(json.dumps(large_metadata).encode('utf-8'))
        }

        artifacts = store_snapshot_files(snapshot_dir, files, validation_config)

        assert 'metadata.json' in artifacts
        assert (snapshot_dir / 'metadata.json').exists()
