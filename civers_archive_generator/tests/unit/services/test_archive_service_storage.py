"""
Tests for ArchiveService StorageManager integration.

These tests verify that ArchiveService correctly initializes and uses
the StorageManager for storing archive metadata.
"""

import pytest
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.unit]


# Mock StorageResult and MultiStorageResult for tests
@dataclass
class MockStorageResult:
    success: bool
    storage_type: str
    storage_location: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class MockMultiStorageResult:
    overall_success: bool
    results: List[MockStorageResult]
    primary_location: Optional[str] = None
    
    def get_successful_backends(self) -> List[str]:
        return [r.storage_type for r in self.results if r.success]
    
    def get_failed_backends(self) -> List[str]:
        return [r.storage_type for r in self.results if not r.success]


class TestArchiveServiceStorageIntegration:
    """Tests for ArchiveService StorageManager integration."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config with storage settings."""
        config = MagicMock()
        config.app.archive_directory = "/tmp/archives"
        config.app.get_storage_config.return_value = MagicMock(
            get_enabled_backends=lambda: ["local_file"],
            backends={"local_file": {"base_path": "archives"}},
            backend="local_file",
            enabled=["local_file"]
        )
        config.domains = []
        return config

    @pytest.fixture
    def mock_storage_manager(self):
        """Create mock StorageManager."""
        manager = AsyncMock()
        manager.store_artifacts.return_value = MockMultiStorageResult(
            overall_success=True,
            results=[MockStorageResult(
                success=True,
                storage_type="local_file",
                storage_location="/tmp/archive_metadata.json"
            )],
            primary_location="/tmp/archive_metadata.json"
        )
        manager.get_enabled_backends.return_value = ["local_file"]
        return manager

    def test_archive_service_initializes_storage_manager(self, mock_config):
        """ArchiveService should initialize StorageManager in __init__."""
        with patch('archive_services.archive_service.StorageManager') as MockStorageManager:
            MockStorageManager.return_value = MagicMock()
            
            from archive_services import ArchiveService
            service = ArchiveService(mock_config)
            
            MockStorageManager.assert_called_once()
            assert hasattr(service, 'storage_manager')

    def test_archive_service_has_storage_manager_attribute(self, mock_config, mock_storage_manager):
        """ArchiveService should have storage_manager attribute after init."""
        with patch('archive_services.archive_service.StorageManager', return_value=mock_storage_manager):
            from archive_services import ArchiveService
            service = ArchiveService(mock_config)
            
            assert service.storage_manager is not None

    @pytest.mark.asyncio
    async def test_store_archive_calls_storage_manager(self, mock_config, mock_storage_manager):
        """_store_archive should call storage_manager.store_metadata."""
        with patch('archive_services.archive_service.StorageManager', return_value=mock_storage_manager):
            from archive_services import ArchiveService
            service = ArchiveService(mock_config)
            
            # Mock domain config
            mock_domain_config = MagicMock()
            mock_domain_config.name = "example.com"
            mock_domain_config.artifacts = ["warc"]
            
            # Create a temp directory structure for testing
            import tempfile
            import os
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create a mock archive file
                archive_file = os.path.join(tmp_dir, "test.warc")
                with open(archive_file, 'w') as f:
                    f.write("mock warc content")
                
                await service._store_archive(
                    archive_path=tmp_dir,
                    _url="https://example.com",
                    domain_config=mock_domain_config,
                    request_id="req_123"
                )
                
                mock_storage_manager.store_artifacts.assert_called_once()
                call_kwargs = mock_storage_manager.store_artifacts.call_args.kwargs
                assert call_kwargs["request_id"] == "req_123"
                assert call_kwargs["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_store_archive_returns_storage_result_info(self, mock_config, mock_storage_manager):
        """_store_archive result should include storage backend info."""
        with patch('archive_services.archive_service.StorageManager', return_value=mock_storage_manager):
            from archive_services import ArchiveService
            service = ArchiveService(mock_config)
            
            mock_domain_config = MagicMock()
            mock_domain_config.name = "example.com"
            mock_domain_config.artifacts = ["warc"]
            
            import tempfile
            import os
            with tempfile.TemporaryDirectory() as tmp_dir:
                archive_file = os.path.join(tmp_dir, "test.warc")
                with open(archive_file, 'w') as f:
                    f.write("mock warc content")
                
                result = await service._store_archive(
                    archive_path=tmp_dir,
                    _url="https://example.com",
                    domain_config=mock_domain_config,
                    request_id="req_123"
                )
                
                # Result should contain storage information
                assert result is not None
                assert "storage_id" in result

    @pytest.mark.asyncio
    async def test_store_archive_handles_storage_failure(self, mock_config, mock_storage_manager):
        """_store_archive should handle storage failures gracefully."""
        mock_storage_manager.store_artifacts.return_value = MockMultiStorageResult(
            overall_success=False,
            results=[MockStorageResult(
                success=False,
                storage_type="local_file",
                error_message="Disk full"
            )],
            primary_location=None
        )
        
        with patch('archive_services.archive_service.StorageManager', return_value=mock_storage_manager):
            from archive_services import ArchiveService
            service = ArchiveService(mock_config)
            
            mock_domain_config = MagicMock()
            mock_domain_config.name = "example.com"
            mock_domain_config.artifacts = ["warc"]
            
            import tempfile
            import os
            with tempfile.TemporaryDirectory() as tmp_dir:
                archive_file = os.path.join(tmp_dir, "test.warc")
                with open(archive_file, 'w') as f:
                    f.write("mock warc content")
                
                # Should not raise, should log and continue
                result = await service._store_archive(
                    archive_path=tmp_dir,
                    _url="https://example.com",
                    domain_config=mock_domain_config,
                    request_id="req_123"
                )
                
                assert result is not None
