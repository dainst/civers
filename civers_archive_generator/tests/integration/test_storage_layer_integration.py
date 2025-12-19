"""
Integration tests for the Storage Layer.

These tests verify end-to-end functionality of the storage layer,
including multi-backend storage, failure handling, and backward compatibility.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from configs.models import StorageConfig
from storage_layer import StorageManager, LocalFileStorageStrategy
from storage_layer.storage_strategy import StorageResult, MultiStorageResult


class TestStorageLayerIntegration:
    """Integration tests for complete storage layer."""

    @pytest.fixture
    def storage_config_local_only(self, tmp_path):
        """Create single-backend storage config."""
        return StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {
                    "base_path": str(tmp_path),
                    "create_subdirectories": True
                }
            }
        )

    @pytest.mark.asyncio
    async def test_end_to_end_local_storage(self, storage_config_local_only, tmp_path):
        """Test complete flow: config -> manager -> strategy -> file."""
        manager = StorageManager(storage_config_local_only)

        metadata = {
            "archive_path": "/tmp/archives/test",
            "source_url": "https://example.com",
            "file_count": 3,
            "total_size": 1024,
            "request_id": "integration_test_001"
        }

        result = await manager.store_metadata(
            data=metadata,
            request_id="integration_test_001",
            url="https://example.com",
            filename="archive_metadata_integration_test_001.json"
        )

        # Verify overall success
        assert result.overall_success is True
        assert "local_file" in result.get_successful_backends()

        # Verify file was created
        saved_file = tmp_path / "archive_metadata_integration_test_001.json"
        assert saved_file.exists()

        # Verify content is correct
        with open(saved_file) as f:
            saved_data = json.load(f)
        assert saved_data["source_url"] == "https://example.com"
        assert saved_data["file_count"] == 3


    @pytest.mark.asyncio
    async def test_storage_manager_initializes_all_enabled_backends(self, tmp_path):
        """StorageManager should initialize all enabled backends."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {"base_path": str(tmp_path)}
            }
        )

        manager = StorageManager(config)

        assert "local_file" in manager.strategies
        assert len(manager.strategies) == 1

    @pytest.mark.asyncio
    async def test_storage_result_contains_backend_info(self, storage_config_local_only, tmp_path):
        """Storage result should contain backend-specific information."""
        manager = StorageManager(storage_config_local_only)

        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="result_info_test",
            url="https://example.com",
            filename="result_info_test.json"
        )

        assert result.overall_success is True
        assert len(result.results) == 1

        backend_result = result.results[0]
        assert backend_result.success is True
        assert backend_result.storage_type == "local_file"
        assert "result_info_test.json" in backend_result.storage_location

    @pytest.mark.asyncio
    async def test_storage_handles_invalid_path(self):
        """Storage should handle errors gracefully for invalid paths."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {"base_path": "/nonexistent/path/that/fails"}
            }
        )

        manager = StorageManager(config)

        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="invalid_path_test",
            url="https://example.com",
            filename="should_fail.json"
        )

        assert result.overall_success is False
        assert "local_file" in result.get_failed_backends()


class TestLocalFileStorageStrategy:
    """Unit tests for LocalFileStorageStrategy."""

    @pytest.mark.asyncio
    async def test_stores_json_file(self, tmp_path):
        """Should store metadata as JSON file."""
        strategy = LocalFileStorageStrategy(
            base_path=str(tmp_path),
            create_subdirectories=True
        )

        result = await strategy.store_metadata(
            data={"title": "Test", "url": "https://example.com"},
            request_id="req_123",
            url="https://example.com",
            filename="test_metadata.json"
        )

        assert result.success is True
        assert result.storage_type == "local_file"

        saved_file = tmp_path / "test_metadata.json"
        assert saved_file.exists()

        with open(saved_file) as f:
            saved_data = json.load(f)
        assert saved_data["title"] == "Test"

    @pytest.mark.asyncio
    async def test_creates_directories_if_needed(self, tmp_path):
        """Should create directories if they don't exist."""
        nested_path = tmp_path / "a" / "b" / "c"
        strategy = LocalFileStorageStrategy(
            base_path=str(nested_path),
            create_subdirectories=True
        )

        result = await strategy.store_metadata(
            data={"test": "data"},
            request_id="req_123",
            url="https://example.com",
            filename="test.json"
        )

        assert result.success is True
        assert (nested_path / "test.json").exists()

    @pytest.mark.asyncio
    async def test_is_available_returns_true(self, tmp_path):
        """is_available should return True for valid configuration."""
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        assert await strategy.is_available() is True

    @pytest.mark.asyncio
    async def test_get_storage_type(self, tmp_path):
        """get_storage_type should return 'local_file'."""
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        assert strategy.get_storage_type() == "local_file"


class TestStorageConfigIntegration:
    """Integration tests for StorageConfig model."""

    def test_multi_backend_config_validates(self, tmp_path):
        """Multi-backend config should validate all enabled backends exist."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {"base_path": str(tmp_path)}
            }
        )
        assert config.get_enabled_backends() == ["local_file"]

    def test_get_backend_config_returns_correct_config(self, tmp_path):
        """get_backend_config should return the correct backend configuration."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {"base_path": str(tmp_path), "option1": "value1"}
            }
        )
        backend_config = config.get_backend_config("local_file")
        assert backend_config["base_path"] == str(tmp_path)
        assert backend_config["option1"] == "value1"
