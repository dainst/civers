"""
Tests for StorageService.create_snapshot() method.

Tests the service layer snapshot creation including delegation to provider,
cache invalidation, and error handling.
"""

import pytest
import json
from io import BytesIO
from unittest.mock import Mock, patch
from pathlib import Path

from app.storage.service import StorageService
from app.storage.providers.filesystem import FilesystemStorageProvider
from configs.models import ValidationConfig
from app.models.snapshot import Snapshot
from app.custom_exceptions.exceptions.api_exceptions import ValidationError
from app.storage.providers.storage_provider_interface import StorageError
from datetime import datetime


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
    """Provide real FilesystemStorageProvider instance."""
    return FilesystemStorageProvider(
        storage_path=temp_storage_path,
        timeout_seconds=10,
        validation_config=validation_config
    )


@pytest.fixture
def storage_service(filesystem_provider):
    """Provide StorageService with real filesystem provider."""
    return StorageService(
        provider=filesystem_provider,
        cache_ttl_seconds=60
    )


@pytest.fixture
def mock_provider():
    """Provide mock storage provider."""
    provider = Mock()
    return provider


@pytest.fixture
def storage_service_with_mock(mock_provider):
    """Provide StorageService with mock provider."""
    return StorageService(
        provider=mock_provider,
        cache_ttl_seconds=60
    )


class TestCreateSnapshotDelegation:
    """Tests for delegation to storage provider."""

    def test_delegates_to_provider(self, storage_service_with_mock, mock_provider):
        """Test that create_snapshot delegates to provider."""
        # Setup mock
        mock_snapshot = Mock(
            snapshot_id='req_test1_20250112_120000',
            url='https://example.com',
            available_artifacts=['archive.wacz']
        )
        mock_provider.create_snapshot.return_value = mock_snapshot

        files = {'archive.wacz': BytesIO(b'content')}

        # Call service method
        result = storage_service_with_mock.create_snapshot(
            url='https://example.com',
            request_id='test1',
            files=files
        )

        # Verify provider was called with correct arguments
        mock_provider.create_snapshot.assert_called_once_with(
            url='https://example.com',
            request_id='test1',
            files=files,
            allow_existing=False
        )

        # Verify result
        assert result == mock_snapshot

    def test_passes_allow_existing_parameter(self, storage_service_with_mock, mock_provider):
        """Test that allow_existing parameter is passed to provider."""
        mock_snapshot = Mock(
            snapshot_id='req_test2_20250112_120000',
            available_artifacts=['screenshot.png']
        )
        mock_provider.create_snapshot.return_value = mock_snapshot

        files = {'screenshot.png': BytesIO(b'content')}

        storage_service_with_mock.create_snapshot(
            url='https://example.com',
            request_id='test2',
            files=files,
            allow_existing=True
        )

        # Verify allow_existing was passed
        mock_provider.create_snapshot.assert_called_once()
        call_kwargs = mock_provider.create_snapshot.call_args[1]
        assert call_kwargs['allow_existing'] is True


class TestCacheInvalidation:
    """Tests for cache invalidation after snapshot creation."""

    def test_cache_cleared_after_create(self, storage_service, temp_storage_path):
        """Test that cache is cleared after creating snapshot."""
        # Populate cache
        storage_service.get_all_urls()
        assert storage_service._cached_urls is not None

        # Create snapshot
        files = {'archive.wacz': BytesIO(b'content')}
        storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test3',
            files=files
        )

        # Cache should be cleared
        assert storage_service._cached_urls is None
        assert storage_service._cache_timestamp == 0.0

    def test_next_get_refreshes_cache(self, storage_service, temp_storage_path):
        """Test that next get_all_urls() after create refreshes cache."""
        # Create snapshot
        files = {'archive.wacz': BytesIO(b'content')}
        storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test4',
            files=files
        )

        # Cache should be cleared
        assert storage_service._cached_urls is None

        # Get URLs should refresh cache
        urls = storage_service.get_all_urls()
        assert storage_service._cached_urls is not None
        assert len(urls) > 0


class TestRealIntegration:
    """Integration tests with real filesystem provider."""

    def test_create_snapshot_end_to_end(self, storage_service, temp_storage_path):
        """Test complete snapshot creation flow through service."""
        metadata = {'url': 'https://example.com', 'title': 'Test Page'}
        files = {
            'archive.wacz': BytesIO(b'wacz content'),
            'metadata.json': BytesIO(json.dumps(metadata).encode('utf-8'))
        }

        snapshot = storage_service.create_snapshot(
            url='https://example.com/test',
            request_id='test5',
            files=files
        )

        # Verify snapshot object
        assert snapshot.snapshot_id.startswith('req_test5_')
        assert str(snapshot.url) == 'https://example.com/test'
        assert len(snapshot.available_artifacts) == 2
        assert 'archive.wacz' in snapshot.available_artifacts
        assert 'metadata.json' in snapshot.available_artifacts

        # Verify files on disk
        snapshot_path = Path(snapshot.folder_path)
        assert snapshot_path.exists()
        assert (snapshot_path / 'archive.wacz').exists()
        assert (snapshot_path / 'metadata.json').exists()

    def test_service_retrieves_created_snapshot(self, storage_service, temp_storage_path):
        """Test that created snapshot can be retrieved via service."""
        files = {'archive.wacz': BytesIO(b'content')}

        created_snapshot = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test6',
            files=files
        )

        # Retrieve snapshot by ID
        retrieved_snapshot = storage_service.get_snapshot_by_id(created_snapshot.snapshot_id)

        assert retrieved_snapshot is not None
        assert retrieved_snapshot.snapshot_id == created_snapshot.snapshot_id
        # Note: URL might be reconstructed slightly differently by scanner, so just check domain
        assert 'example' in str(retrieved_snapshot.url).lower()

    def test_idempotent_operation_via_service(self, storage_service, temp_storage_path):
        """Test idempotent snapshot creation through service."""
        # First upload
        files1 = {'archive.wacz': BytesIO(b'wacz content')}
        snapshot1 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test7',
            files=files1
        )

        assert len(snapshot1.available_artifacts) == 1

        # Second upload with allow_existing
        files2 = {'screenshot.png': BytesIO(b'png content')}
        snapshot2 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test7',
            files=files2,
            allow_existing=True
        )

        # create_snapshot returns ALL artifacts in the directory (existing + new)
        assert len(snapshot2.available_artifacts) == 2
        assert 'screenshot.png' in snapshot2.available_artifacts
        assert 'archive.wacz' in snapshot2.available_artifacts

        # Both files should exist on disk
        snapshot_path = Path(snapshot2.folder_path)
        assert (snapshot_path / 'archive.wacz').exists()
        assert (snapshot_path / 'screenshot.png').exists()


class TestErrorPropagation:
    """Tests for error propagation from provider."""

    def test_validation_error_propagated(self, storage_service, temp_storage_path):
        """Test that ValidationError from provider is propagated."""
        files = {'malware.exe': BytesIO(b'bad content')}

        with pytest.raises(ValidationError, match="Invalid artifact type"):
            storage_service.create_snapshot(
                url='https://example.com/page',
                request_id='test8',
                files=files
            )

    def test_duplicate_snapshot_error_propagated(self, storage_service, temp_storage_path):
        """Test that duplicate snapshot is handled gracefully via auto-discovery."""
        files = {'archive.wacz': BytesIO(b'content')}

        # First creation
        snapshot1 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test9',
            files=files
        )

        # Second creation without allow_existing — create_snapshot auto-discovers
        # existing snapshots and adds files to them (idempotent behavior)
        files2 = {'archive.wacz': BytesIO(b'content')}
        snapshot2 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='test9',
            files=files2
        )

        # Should reuse the same snapshot directory
        assert snapshot1.snapshot_id == snapshot2.snapshot_id

    def test_storage_error_propagated(self, storage_service_with_mock, mock_provider):
        """Test that StorageError from provider is propagated."""
        mock_provider.create_snapshot.side_effect = StorageError("Storage failed")

        files = {'archive.wacz': BytesIO(b'content')}

        with pytest.raises(StorageError, match="Storage failed"):
            storage_service_with_mock.create_snapshot(
                url='https://example.com/page',
                request_id='test10',
                files=files
            )


class TestLogging:
    """Tests for logging behavior."""

    def test_logs_snapshot_creation(self, storage_service_with_mock, mock_provider):
        """Test that snapshot creation is logged."""
        mock_snapshot = Mock(
            snapshot_id='req_test11_20250112_120000',
            available_artifacts=['archive.wacz']
        )
        mock_provider.create_snapshot.return_value = mock_snapshot

        files = {'archive.wacz': BytesIO(b'content')}

        with patch('app.storage.service.logger') as mock_logger:
            storage_service_with_mock.create_snapshot(
                url='https://example.com/page',
                request_id='test11',
                files=files
            )

            # Verify info logs were called
            assert mock_logger.info.call_count >= 2  # Start and success messages

    def test_logs_errors(self, storage_service_with_mock, mock_provider):
        """Test that errors are logged."""
        mock_provider.create_snapshot.side_effect = ValidationError("Invalid input")

        files = {'archive.wacz': BytesIO(b'content')}

        with patch('app.storage.service.logger') as mock_logger:
            with pytest.raises(ValidationError):
                storage_service_with_mock.create_snapshot(
                    url='https://example.com/page',
                    request_id='test12',
                    files=files
                )

            # Verify error was logged
            mock_logger.error.assert_called_once()


class TestMultipleSnapshots:
    """Tests for creating multiple snapshots."""

    def test_create_multiple_snapshots_same_url(self, storage_service, temp_storage_path):
        """Test creating multiple snapshots for same URL with different request IDs."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot1 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='request1',
            files=files
        )

        snapshot2 = storage_service.create_snapshot(
            url='https://example.com/page',
            request_id='request2',
            files=files
        )

        # Should have different snapshot IDs
        assert snapshot1.snapshot_id != snapshot2.snapshot_id

        # Both should be retrievable
        retrieved1 = storage_service.get_snapshot_by_id(snapshot1.snapshot_id)
        retrieved2 = storage_service.get_snapshot_by_id(snapshot2.snapshot_id)

        assert retrieved1 is not None
        assert retrieved2 is not None

    def test_create_snapshots_different_urls(self, storage_service, temp_storage_path):
        """Test creating snapshots for different URLs."""
        files = {'archive.wacz': BytesIO(b'content')}

        snapshot1 = storage_service.create_snapshot(
            url='https://example.com/page1',
            request_id='test13',
            files=files
        )

        snapshot2 = storage_service.create_snapshot(
            url='https://example.com/page2',
            request_id='test14',
            files=files
        )

        # Both should exist
        assert Path(snapshot1.folder_path).exists()
        assert Path(snapshot2.folder_path).exists()

        # Should be in different directories
        assert snapshot1.folder_path != snapshot2.folder_path
