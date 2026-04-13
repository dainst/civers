"""
Tests for Local File Storage Strategy.

Tests the LocalFileStorageStrategy implementation including successful storage,
directory creation, error handling, and availability checking.
"""

import json

import pytest

from storage_layer.local_file_storage_strategy import LocalFileStorageStrategy


class TestLocalFileStorageStrategy:
    """Test cases for LocalFileStorageStrategy."""

    @pytest.mark.asyncio
    async def test_successful_storage(self, tmp_path):
        """Test successful metadata storage to local file."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"title": "Test Metadata", "description": "Test description", "items": [1, 2, 3]}

        # Act
        result = await strategy.store_metadata(
            data=data,
            request_id="test_001",
            url="https://example.com",
            filename="test_metadata.json",
        )

        # Assert
        assert result.success is True
        assert result.storage_type == "local_file"
        assert result.storage_location is not None
        assert result.error_message is None

        # Verify file was created
        expected_path = tmp_path / "test_metadata.json"
        assert expected_path.exists()

        # Verify file content
        with open(expected_path) as f:
            saved_data = json.load(f)
        assert saved_data == data

    @pytest.mark.asyncio
    async def test_storage_location_in_result(self, tmp_path):
        """Test that storage location is correctly returned in result."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"test": "data"}
        filename = "metadata_test_123.json"

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_123", url="https://example.com", filename=filename
        )

        # Assert
        expected_path = str(tmp_path / filename)
        assert result.storage_location == expected_path
        assert result.metadata["filepath"] == expected_path
        assert result.metadata["filename"] == filename

    @pytest.mark.asyncio
    async def test_directory_created_if_missing(self, tmp_path):
        """Test that base directory is created if it doesn't exist."""
        # Arrange
        nested_path = tmp_path / "level1" / "level2" / "metadata"
        strategy = LocalFileStorageStrategy(base_path=str(nested_path), create_subdirectories=True)
        data = {"test": "data"}

        # Verify directory doesn't exist yet
        assert not nested_path.exists()

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="test.json"
        )

        # Assert
        assert result.success is True
        assert nested_path.exists()
        assert (nested_path / "test.json").exists()

    @pytest.mark.asyncio
    async def test_json_formatting(self, tmp_path):
        """Test that JSON is properly formatted with indentation."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"nested": {"object": {"value": "test"}}}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="formatted.json"
        )

        # Assert
        filepath = tmp_path / "formatted.json"
        content = filepath.read_text()

        # Should have indentation and newlines
        assert "\n" in content
        assert "  " in content  # 2-space indent

        # Should parse back to same data
        parsed = json.loads(content)
        assert parsed == data

    @pytest.mark.asyncio
    async def test_metadata_includes_file_size(self, tmp_path):
        """Test that result includes file size in metadata."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"test": "data" * 100}  # Create some content

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="sized.json"
        )

        # Assert
        assert "size_bytes" in result.metadata
        assert result.metadata["size_bytes"] > 0

        # Verify size is accurate
        filepath = tmp_path / "sized.json"
        actual_size = filepath.stat().st_size
        assert result.metadata["size_bytes"] == actual_size

    @pytest.mark.asyncio
    async def test_handles_non_serializable_data(self, tmp_path):
        """Test that strategy handles non-serializable objects using default=str."""
        from datetime import datetime

        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"created_at": datetime(2024, 1, 15, 10, 30), "regular": "string"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="datetime.json"
        )

        # Assert - should succeed by converting datetime to string
        assert result.success is True

        # Verify file content
        filepath = tmp_path / "datetime.json"
        with open(filepath) as f:
            saved = json.load(f)

        assert saved["regular"] == "string"
        assert isinstance(saved["created_at"], str)  # Converted to string

    @pytest.mark.asyncio
    async def test_handles_unicode_content(self, tmp_path):
        """Test that strategy correctly handles unicode characters."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"title": "Archäologisches Objekt", "description": "测试数据", "emoji": "🏛️"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="unicode.json"
        )

        # Assert
        assert result.success is True

        # Verify unicode is preserved
        filepath = tmp_path / "unicode.json"
        with open(filepath, encoding="utf-8") as f:
            saved = json.load(f)

        assert saved["title"] == "Archäologisches Objekt"
        assert saved["description"] == "测试数据"
        assert saved["emoji"] == "🏛️"

    @pytest.mark.asyncio
    async def test_error_handling_invalid_path(self):
        """Test error handling for invalid filesystem paths."""
        # Arrange - use invalid path (e.g., path with null byte)
        try:
            invalid_path = "/tmp/test\x00invalid"
            strategy = LocalFileStorageStrategy(base_path=invalid_path)
            data = {"test": "data"}

            # Act
            result = await strategy.store_metadata(
                data=data, request_id="test_001", url="https://example.com", filename="test.json"
            )

            # Assert
            assert result.success is False
            assert result.error_message is not None
            assert "error" in result.error_message.lower()
        except ValueError:
            # Some systems may reject the path immediately
            pytest.skip("System rejects invalid path immediately")

    @pytest.mark.asyncio
    async def test_get_storage_type(self, tmp_path):
        """Test that get_storage_type returns correct identifier."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))

        # Act
        storage_type = strategy.get_storage_type()

        # Assert
        assert storage_type == "local_file"

    @pytest.mark.asyncio
    async def test_is_available_success(self, tmp_path):
        """Test is_available returns True when directory is accessible."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))

        # Act
        available = await strategy.is_available()

        # Assert
        assert available is True

    @pytest.mark.asyncio
    async def test_is_available_creates_directory(self, tmp_path):
        """Test that is_available creates the directory if needed."""
        # Arrange
        new_dir = tmp_path / "new_storage"
        strategy = LocalFileStorageStrategy(base_path=str(new_dir))

        # Verify directory doesn't exist
        assert not new_dir.exists()

        # Act
        available = await strategy.is_available()

        # Assert
        assert available is True
        assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_multiple_files_same_directory(self, tmp_path):
        """Test storing multiple files to the same directory."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))

        # Act - store multiple files
        results = []
        for i in range(3):
            result = await strategy.store_metadata(
                data={"file_number": i},
                request_id=f"test_{i:03d}",
                url="https://example.com",
                filename=f"metadata_{i}.json",
            )
            results.append(result)

        # Assert
        assert all(r.success for r in results)

        # Verify all files exist
        for i in range(3):
            filepath = tmp_path / f"metadata_{i}.json"
            assert filepath.exists()

    @pytest.mark.asyncio
    async def test_custom_base_path(self, tmp_path):
        """Test that custom base_path is respected."""
        # Arrange
        custom_path = tmp_path / "custom" / "storage" / "location"
        strategy = LocalFileStorageStrategy(base_path=str(custom_path))
        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="test.json"
        )

        # Assert
        assert result.success is True
        expected_file = custom_path / "test.json"
        assert expected_file.exists()
        assert result.storage_location == str(expected_file)

    @pytest.mark.asyncio
    async def test_result_metadata_completeness(self, tmp_path):
        """Test that result metadata contains all expected fields."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {"test": "data"}
        filename = "complete.json"

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename=filename
        )

        # Assert
        assert "filepath" in result.metadata
        assert "size_bytes" in result.metadata
        assert "base_path" in result.metadata
        assert "filename" in result.metadata

        assert result.metadata["filename"] == filename
        assert result.metadata["base_path"] == str(tmp_path)

    @pytest.mark.asyncio
    async def test_empty_data_storage(self, tmp_path):
        """Test storing empty dictionary."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        data = {}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="empty.json"
        )

        # Assert
        assert result.success is True

        # Verify file contains empty object
        filepath = tmp_path / "empty.json"
        with open(filepath) as f:
            saved = json.load(f)
        assert saved == {}

    @pytest.mark.asyncio
    async def test_large_data_storage(self, tmp_path):
        """Test storing large metadata object."""
        # Arrange
        strategy = LocalFileStorageStrategy(base_path=str(tmp_path))
        # Create large data structure
        data = {f"field_{i}": f"value_{i}" * 100 for i in range(1000)}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="test_001", url="https://example.com", filename="large.json"
        )

        # Assert
        assert result.success is True
        assert result.metadata["size_bytes"] > 10000  # Should be fairly large

        # Verify content
        filepath = tmp_path / "large.json"
        with open(filepath) as f:
            saved = json.load(f)
        assert len(saved) == 1000
