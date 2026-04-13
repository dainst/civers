"""
Tests for Storage Strategy Interface and Result Models.

Tests the StorageResult and MultiStorageResult dataclasses and their helper methods.
"""

from datetime import datetime

import pytest

from storage_layer.storage_strategy import MultiStorageResult, StorageResult, StorageStrategy


class TestStorageResult:
    """Test cases for StorageResult dataclass."""

    def test_create_successful_result(self):
        """Test creating a successful StorageResult."""
        result = StorageResult(
            success=True, storage_type="local_file", storage_location="/path/to/file.json"
        )

        assert result.success is True
        assert result.storage_type == "local_file"
        assert result.storage_location == "/path/to/file.json"
        assert result.error_message is None
        assert result.metadata == {}
        assert result.created_at is not None

    def test_create_failed_result(self):
        """Test creating a failed StorageResult with error message."""
        result = StorageResult(
            success=False, storage_type="civers_rest_api", error_message="Connection timeout"
        )

        assert result.success is False
        assert result.storage_type == "civers_rest_api"
        assert result.storage_location is None
        assert result.error_message == "Connection timeout"

    def test_result_with_metadata(self):
        """Test StorageResult with additional metadata."""
        result = StorageResult(
            success=True,
            storage_type="local_file",
            storage_location="/path/file.json",
            metadata={"size_bytes": 1024, "filename": "metadata.json"},
        )

        assert result.metadata["size_bytes"] == 1024
        assert result.metadata["filename"] == "metadata.json"

    def test_created_at_is_iso_format(self):
        """Test that created_at is in ISO format."""
        result = StorageResult(success=True, storage_type="test")

        # Should be able to parse as ISO format
        parsed = datetime.fromisoformat(result.created_at)
        assert isinstance(parsed, datetime)

    def test_default_metadata_is_empty_dict(self):
        """Test that metadata defaults to empty dict, not None."""
        result = StorageResult(success=True, storage_type="test")

        assert result.metadata == {}
        assert isinstance(result.metadata, dict)


class TestMultiStorageResult:
    """Test cases for MultiStorageResult dataclass."""

    def test_create_multi_result_all_success(self):
        """Test MultiStorageResult when all backends succeed."""
        results = [
            StorageResult(
                success=True, storage_type="local_file", storage_location="/path/file.json"
            ),
            StorageResult(
                success=True, storage_type="civers_rest_api", storage_location="snapshot_123"
            ),
        ]

        multi_result = MultiStorageResult(
            overall_success=True, results=results, primary_location="/path/file.json"
        )

        assert multi_result.overall_success is True
        assert len(multi_result.results) == 2
        assert multi_result.primary_location == "/path/file.json"

    def test_create_multi_result_partial_success(self):
        """Test MultiStorageResult when some backends fail."""
        results = [
            StorageResult(
                success=True, storage_type="local_file", storage_location="/path/file.json"
            ),
            StorageResult(success=False, storage_type="civers_rest_api", error_message="API down"),
        ]

        multi_result = MultiStorageResult(
            overall_success=True,  # At least one succeeded
            results=results,
            primary_location="/path/file.json",
        )

        assert multi_result.overall_success is True
        assert len(multi_result.get_successful_backends()) == 1
        assert len(multi_result.get_failed_backends()) == 1

    def test_create_multi_result_all_failed(self):
        """Test MultiStorageResult when all backends fail."""
        results = [
            StorageResult(success=False, storage_type="local_file", error_message="Disk full"),
            StorageResult(
                success=False, storage_type="civers_rest_api", error_message="Network error"
            ),
        ]

        multi_result = MultiStorageResult(
            overall_success=False, results=results, primary_location=None
        )

        assert multi_result.overall_success is False
        assert multi_result.primary_location is None
        assert len(multi_result.get_successful_backends()) == 0
        assert len(multi_result.get_failed_backends()) == 2

    def test_get_result_by_type_found(self):
        """Test getting result by storage type when it exists."""
        results = [
            StorageResult(
                success=True, storage_type="local_file", storage_location="/path/file.json"
            ),
            StorageResult(
                success=True, storage_type="civers_rest_api", storage_location="snapshot_123"
            ),
        ]

        multi_result = MultiStorageResult(overall_success=True, results=results)

        local_result = multi_result.get_result_by_type("local_file")
        assert local_result is not None
        assert local_result.storage_type == "local_file"
        assert local_result.storage_location == "/path/file.json"

        api_result = multi_result.get_result_by_type("civers_rest_api")
        assert api_result is not None
        assert api_result.storage_type == "civers_rest_api"
        assert api_result.storage_location == "snapshot_123"

    def test_get_result_by_type_not_found(self):
        """Test getting result by storage type when it doesn't exist."""
        results = [
            StorageResult(
                success=True, storage_type="local_file", storage_location="/path/file.json"
            )
        ]

        multi_result = MultiStorageResult(overall_success=True, results=results)

        s3_result = multi_result.get_result_by_type("s3")
        assert s3_result is None

    def test_get_successful_backends_mixed(self):
        """Test get_successful_backends with mixed success/failure."""
        results = [
            StorageResult(success=True, storage_type="local_file", storage_location="/path"),
            StorageResult(success=False, storage_type="civers_rest_api", error_message="Error"),
            StorageResult(success=True, storage_type="s3", storage_location="s3://bucket/key"),
        ]

        multi_result = MultiStorageResult(overall_success=True, results=results)

        successful = multi_result.get_successful_backends()
        assert len(successful) == 2
        assert "local_file" in successful
        assert "s3" in successful
        assert "civers_rest_api" not in successful

    def test_get_successful_backends_empty(self):
        """Test get_successful_backends when all failed."""
        results = [
            StorageResult(success=False, storage_type="local_file", error_message="Error"),
            StorageResult(success=False, storage_type="s3", error_message="Error"),
        ]

        multi_result = MultiStorageResult(overall_success=False, results=results)

        successful = multi_result.get_successful_backends()
        assert len(successful) == 0
        assert successful == []

    def test_get_failed_backends_mixed(self):
        """Test get_failed_backends with mixed success/failure."""
        results = [
            StorageResult(success=True, storage_type="local_file", storage_location="/path"),
            StorageResult(success=False, storage_type="civers_rest_api", error_message="Error"),
            StorageResult(success=False, storage_type="s3", error_message="Error"),
        ]

        multi_result = MultiStorageResult(overall_success=True, results=results)

        failed = multi_result.get_failed_backends()
        assert len(failed) == 2
        assert "civers_rest_api" in failed
        assert "s3" in failed
        assert "local_file" not in failed

    def test_get_failed_backends_empty(self):
        """Test get_failed_backends when all succeeded."""
        results = [
            StorageResult(success=True, storage_type="local_file", storage_location="/path"),
            StorageResult(success=True, storage_type="s3", storage_location="s3://bucket"),
        ]

        multi_result = MultiStorageResult(overall_success=True, results=results)

        failed = multi_result.get_failed_backends()
        assert len(failed) == 0
        assert failed == []

    def test_empty_results_list(self):
        """Test MultiStorageResult with empty results list."""
        multi_result = MultiStorageResult(overall_success=False, results=[])

        assert multi_result.overall_success is False
        assert len(multi_result.results) == 0
        assert multi_result.get_successful_backends() == []
        assert multi_result.get_failed_backends() == []
        assert multi_result.get_result_by_type("any_type") is None


class TestStorageStrategy:
    """Test cases for StorageStrategy abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that StorageStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageStrategy()

    def test_must_implement_store_metadata(self):
        """Test that subclass must implement store_metadata."""

        class IncompleteStrategy(StorageStrategy):
            def get_storage_type(self):
                return "test"

            async def is_available(self):
                return True

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_must_implement_get_storage_type(self):
        """Test that subclass must implement get_storage_type."""

        class IncompleteStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                pass

            async def is_available(self):
                return True

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_must_implement_is_available(self):
        """Test that subclass must implement is_available."""

        class IncompleteStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                pass

            def get_storage_type(self):
                return "test"

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_complete_implementation(self):
        """Test that complete implementation can be instantiated."""

        class CompleteStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(success=True, storage_type="test")

            def get_storage_type(self):
                return "test"

            async def is_available(self):
                return True

        # Should not raise
        strategy = CompleteStrategy()
        assert strategy is not None
        assert strategy.get_storage_type() == "test"

    @pytest.mark.asyncio
    async def test_strategy_methods_callable(self):
        """Test that implemented strategy methods are callable."""

        class TestStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(
                    success=True, storage_type="test", storage_location="test_location"
                )

            def get_storage_type(self):
                return "test_strategy"

            async def is_available(self):
                return True

        strategy = TestStrategy()

        # Test get_storage_type
        storage_type = strategy.get_storage_type()
        assert storage_type == "test_strategy"

        # Test is_available
        available = await strategy.is_available()
        assert available is True

        # Test store_metadata
        result = await strategy.store_metadata(
            data={"test": "data"},
            request_id="req_123",
            url="https://example.com",
            filename="test.json",
        )
        assert result.success is True
        assert result.storage_type == "test"
        assert result.storage_location == "test_location"
