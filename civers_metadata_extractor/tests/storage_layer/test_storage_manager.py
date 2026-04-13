"""
Tests for Storage Manager.

Tests the StorageManager multi-backend coordinator including initialization,
storage coordination, result aggregation, and error handling.
"""

from typing import Any

import pytest

from storage_layer.storage_manager import StorageManager
from storage_layer.storage_strategy import StorageResult, StorageStrategy
from storage_layer.strategy_registry import StorageStrategyRegistry


# Mock config class for testing (supports both single and multi-backend)
class MockStorageConfig:
    """Mock storage config for testing."""

    def __init__(
        self,
        enabled: list[str] = None,
        backend: str = None,
        backends: dict[str, dict[str, Any]] = None,
    ):
        # Support both old (backend) and new (enabled) config formats
        if enabled is not None:
            self._enabled = enabled
        elif backend is not None:
            self._enabled = [backend]
        else:
            self._enabled = ["mock_success"]

        self.backends = backends or {}

    def get_enabled_backends(self) -> list[str]:
        return self._enabled


# Mock strategy for testing
class MockSuccessStrategy(StorageStrategy):
    """Mock strategy that always succeeds."""

    def __init__(self, **kwargs):
        self.config = kwargs
        self.storage_type_name = "mock_success"

    async def store_metadata(self, data, request_id, url, filename):
        return StorageResult(
            success=True,
            storage_type=self.storage_type_name,
            storage_location=f"/mock/path/{filename}",
        )

    def get_storage_type(self):
        return self.storage_type_name

    async def is_available(self):
        return True


class MockFailStrategy(StorageStrategy):
    """Mock strategy that always fails."""

    def __init__(self, **kwargs):
        self.config = kwargs
        self.storage_type_name = "mock_fail"

    async def store_metadata(self, data, request_id, url, filename):
        return StorageResult(
            success=False, storage_type=self.storage_type_name, error_message="Mock failure"
        )

    def get_storage_type(self):
        return self.storage_type_name

    async def is_available(self):
        return True


class MockUnavailableStrategy(StorageStrategy):
    """Mock strategy that reports as unavailable."""

    def __init__(self, **kwargs):
        self.config = kwargs
        self.storage_type_name = "mock_unavailable"

    async def store_metadata(self, data, request_id, url, filename):
        # Should not be called if unavailable
        return StorageResult(
            success=False, storage_type=self.storage_type_name, error_message="Should not be called"
        )

    def get_storage_type(self):
        return self.storage_type_name

    async def is_available(self):
        return False


class TestStorageManagerInitialization:
    """Test StorageManager initialization."""

    def setup_method(self):
        """Clear registry and register mock strategies."""
        StorageStrategyRegistry.clear_registry()
        StorageStrategyRegistry.register("mock_success", MockSuccessStrategy)
        StorageStrategyRegistry.register("mock_fail", MockFailStrategy)
        StorageStrategyRegistry.register("mock_unavailable", MockUnavailableStrategy)

    def test_initialization_with_single_backend(self):
        """Test initialization with one enabled backend."""
        config = MockStorageConfig(
            enabled=["mock_success"], backends={"mock_success": {"param1": "value1"}}
        )

        manager = StorageManager(config)

        assert len(manager.strategies) == 1
        assert "mock_success" in manager.strategies

    def test_initialization_with_multiple_backends(self):
        """Test initialization with multiple enabled backends."""
        config = MockStorageConfig(
            enabled=["mock_success", "mock_fail"], backends={"mock_success": {}, "mock_fail": {}}
        )

        manager = StorageManager(config)

        assert len(manager.strategies) == 2
        assert "mock_success" in manager.strategies
        assert "mock_fail" in manager.strategies

    def test_initialization_skips_backend_without_config(self):
        """Test that backends without config are skipped."""
        config = MockStorageConfig(
            enabled=["mock_success", "missing_config"], backends={"mock_success": {}}
        )

        manager = StorageManager(config)

        # Should only have mock_success, not missing_config
        assert len(manager.strategies) == 1
        assert "mock_success" in manager.strategies
        assert "missing_config" not in manager.strategies

    def test_initialization_continues_if_backend_fails(self):
        """Test that initialization continues even if one backend fails."""
        config = MockStorageConfig(
            enabled=["mock_success", "nonexistent_backend"],
            backends={"mock_success": {}, "nonexistent_backend": {}},
        )

        manager = StorageManager(config)

        # Should have successful backend even though one failed
        assert len(manager.strategies) == 1
        assert "mock_success" in manager.strategies

    def test_get_enabled_backends(self):
        """Test get_enabled_backends returns correct list."""
        config = MockStorageConfig(
            enabled=["mock_success", "mock_fail"], backends={"mock_success": {}, "mock_fail": {}}
        )

        manager = StorageManager(config)
        enabled = manager.get_enabled_backends()

        assert len(enabled) == 2
        assert "mock_success" in enabled
        assert "mock_fail" in enabled

    def test_get_backend_strategy_success(self):
        """Test getting a strategy instance by name."""
        config = MockStorageConfig(enabled=["mock_success"], backends={"mock_success": {}})

        manager = StorageManager(config)
        strategy = manager.get_backend_strategy("mock_success")

        assert isinstance(strategy, MockSuccessStrategy)

    def test_get_backend_strategy_not_found(self):
        """Test get_backend_strategy raises error for unknown backend."""
        config = MockStorageConfig(enabled=["mock_success"], backends={"mock_success": {}})

        manager = StorageManager(config)

        with pytest.raises(KeyError, match="not initialized"):
            manager.get_backend_strategy("nonexistent")


class TestStorageManagerOperation:
    """Test StorageManager storage operations."""

    def setup_method(self):
        """Clear registry and register mock strategies."""
        StorageStrategyRegistry.clear_registry()
        StorageStrategyRegistry.register("mock_success", MockSuccessStrategy)
        StorageStrategyRegistry.register("mock_fail", MockFailStrategy)
        StorageStrategyRegistry.register("mock_unavailable", MockUnavailableStrategy)

    @pytest.mark.asyncio
    async def test_store_metadata_single_backend_success(self):
        """Test storing to a single successful backend."""
        config = MockStorageConfig(enabled=["mock_success"], backends={"mock_success": {}})

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_001",
            url="https://example.com",
            filename="test.json",
        )

        assert result.overall_success is True
        assert len(result.results) == 1
        assert result.results[0].success is True
        assert result.primary_location is not None

    @pytest.mark.asyncio
    async def test_store_metadata_multiple_backends_all_succeed(self):
        """Test storing to multiple backends where all succeed."""
        config = MockStorageConfig(
            enabled=["mock_success", "mock_success"],  # Two success backends
            backends={"mock_success": {}},
        )

        # Register second mock strategy
        class MockSuccess2(MockSuccessStrategy):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.storage_type_name = "mock_success2"

        StorageStrategyRegistry.register("mock_success2", MockSuccess2)

        config = MockStorageConfig(
            enabled=["mock_success", "mock_success2"],
            backends={"mock_success": {}, "mock_success2": {}},
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_002",
            url="https://example.com",
            filename="test.json",
        )

        assert result.overall_success is True
        assert len(result.results) == 2
        assert all(r.success for r in result.results)

    @pytest.mark.asyncio
    async def test_store_metadata_single_backend_failure(self):
        """Test storing to a single backend that fails."""
        config = MockStorageConfig(enabled=["mock_fail"], backends={"mock_fail": {}})

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_003",
            url="https://example.com",
            filename="test.json",
        )

        assert result.overall_success is False
        assert len(result.results) == 1
        assert result.results[0].success is False
        assert result.primary_location is None

    @pytest.mark.asyncio
    async def test_store_metadata_mixed_success_and_failure(self):
        """Test with some backends succeeding and some failing."""
        config = MockStorageConfig(
            enabled=["mock_success", "mock_fail"], backends={"mock_success": {}, "mock_fail": {}}
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_004",
            url="https://example.com",
            filename="test.json",
        )

        # Overall should succeed because one backend succeeded
        assert result.overall_success is True
        assert len(result.results) == 2

        successful = result.get_successful_backends()
        failed = result.get_failed_backends()

        assert len(successful) == 1
        assert len(failed) == 1
        assert "mock_success" in successful
        assert "mock_fail" in failed

    @pytest.mark.asyncio
    async def test_store_metadata_skips_unavailable_backend(self):
        """Test that unavailable backends are skipped."""
        config = MockStorageConfig(
            enabled=["mock_unavailable", "mock_success"],
            backends={"mock_unavailable": {}, "mock_success": {}},
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_005",
            url="https://example.com",
            filename="test.json",
        )

        assert result.overall_success is True
        assert len(result.results) == 2

        # Unavailable should have been skipped (marked as failed)
        for r in result.results:
            if r.storage_type == "mock_unavailable":
                assert r.success is False
                assert "not available" in r.error_message.lower()

    @pytest.mark.asyncio
    async def test_primary_location_prefers_local_file(self):
        """Test that primary location prefers local_file backend."""

        # Register mock local_file
        class MockLocalFile(MockSuccessStrategy):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.storage_type_name = "local_file"

            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(
                    success=True,
                    storage_type="local_file",
                    storage_location="/local/path/file.json",
                )

        StorageStrategyRegistry.register("local_file", MockLocalFile)

        config = MockStorageConfig(
            enabled=["mock_success", "local_file"], backends={"mock_success": {}, "local_file": {}}
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_006",
            url="https://example.com",
            filename="test.json",
        )

        # Primary location should be from local_file
        assert result.primary_location == "/local/path/file.json"

    @pytest.mark.asyncio
    async def test_primary_location_fallback_when_no_local_file(self):
        """Test that primary location falls back to first successful."""
        config = MockStorageConfig(
            enabled=["mock_success", "mock_fail"], backends={"mock_success": {}, "mock_fail": {}}
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_007",
            url="https://example.com",
            filename="test.json",
        )

        # Primary location should be from mock_success
        assert result.primary_location is not None
        assert "/mock/path/" in result.primary_location

    @pytest.mark.asyncio
    async def test_no_enabled_backends(self):
        """Test behavior when no backends are enabled."""
        config = MockStorageConfig(enabled=[], backends={})

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "data"},
            request_id="test_008",
            url="https://example.com",
            filename="test.json",
        )

        assert result.overall_success is False
        assert len(result.results) == 0
        assert result.primary_location is None


class TestStorageManagerRealStrategies:
    """Test StorageManager with real strategy implementations."""

    def setup_method(self):
        """Register real strategies."""
        from storage_layer.civers_rest_api_storage_strategy import CiversRestApiStorageStrategy
        from storage_layer.local_file_storage_strategy import LocalFileStorageStrategy

        StorageStrategyRegistry.clear_registry()
        StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)

    def test_create_local_file_strategy_instance(self):
        """Test creating local_file strategy with config."""
        config = MockStorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "test/output", "create_subdirectories": False}},
        )

        manager = StorageManager(config)
        strategy = manager.get_backend_strategy("local_file")

        assert strategy is not None
        assert strategy.get_storage_type() == "local_file"

    def test_create_civers_rest_api_strategy_instance(self):
        """Test creating civers_rest_api strategy with config."""
        config = MockStorageConfig(
            enabled=["civers_rest_api"],
            backends={
                "civers_rest_api": {
                    "upload_url": "http://test.example.com/upload",
                    "timeout_seconds": 60,
                    "retry_attempts": 5,
                    "verify_ssl": False,
                    "auth": {"enabled": False},
                }
            },
        )

        manager = StorageManager(config)
        strategy = manager.get_backend_strategy("civers_rest_api")

        assert strategy is not None
        assert strategy.get_storage_type() == "civers_rest_api"

    @pytest.mark.asyncio
    async def test_store_with_local_file_backend(self, tmp_path):
        """Test actual storage with local_file backend."""
        config = MockStorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": str(tmp_path), "create_subdirectories": True}},
        )

        manager = StorageManager(config)
        result = await manager.store_metadata(
            data={"test": "real_data"},
            request_id="real_test_001",
            url="https://example.com",
            filename="real_test.json",
        )

        assert result.overall_success is True
        assert len(result.results) == 1
        assert result.results[0].success is True
        assert result.primary_location is not None

        # Verify file was actually created
        import json

        with open(result.primary_location) as f:
            stored_data = json.load(f)
        assert stored_data == {"test": "real_data"}
