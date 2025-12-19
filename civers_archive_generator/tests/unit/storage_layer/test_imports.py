"""
Tests for storage_layer imports.

These tests verify that the storage_layer package can be imported correctly
after fixing the import paths from 'configs' to 'config'.
"""

import pytest


class TestStorageLayerImports:
    """Tests to verify storage_layer imports work correctly."""

    def test_can_import_storage_manager(self):
        """Storage manager module should be importable."""
        from storage_layer import StorageManager
        assert StorageManager is not None

    def test_can_import_local_file_strategy(self):
        """Local file storage strategy should be importable."""
        from storage_layer import LocalFileStorageStrategy
        assert LocalFileStorageStrategy is not None

    def test_can_import_civers_api_strategy(self):
        """CIVERS REST API storage strategy should be importable."""
        from storage_layer import CiversRestApiStorageStrategy
        assert CiversRestApiStorageStrategy is not None

    def test_can_import_storage_result_types(self):
        """Storage result dataclasses should be importable."""
        from storage_layer import StorageResult, MultiStorageResult
        assert StorageResult is not None
        assert MultiStorageResult is not None

    def test_can_import_storage_strategy_base(self):
        """StorageStrategy base class should be importable."""
        from storage_layer import StorageStrategy
        assert StorageStrategy is not None

    def test_can_import_storage_strategy_registry(self):
        """StorageStrategyRegistry should be importable."""
        from storage_layer import StorageStrategyRegistry
        assert StorageStrategyRegistry is not None

    def test_storage_manager_uses_correct_logger(self):
        """StorageManager should use get_logger from configs.logging_config."""
        from storage_layer.storage_manager import get_logger
        from configs.logging_config import get_logger as expected_logger
        assert get_logger is expected_logger

    def test_local_file_strategy_uses_correct_logger(self):
        """LocalFileStorageStrategy should use get_logger from configs.logging_config."""
        from storage_layer.local_file_storage_strategy import get_logger
        from configs.logging_config import get_logger as expected_logger
        assert get_logger is expected_logger

    def test_civers_api_strategy_uses_correct_logger(self):
        """CiversRestApiStorageStrategy should use get_logger from configs.logging_config."""
        from storage_layer.civers_rest_api_storage_strategy import get_logger
        from configs.logging_config import get_logger as expected_logger
        assert get_logger is expected_logger
