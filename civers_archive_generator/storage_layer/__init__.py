"""Backends for publishing capture files. Generators already save files locally."""

from .storage_strategy import StorageStrategy, StorageResult, MultiStorageResult
from .civers_rest_api_storage_strategy import CiversRestApiStorageStrategy
from .strategy_registry import StorageStrategyRegistry
from .storage_manager import StorageManager

# Register built-in storage strategies
StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)


__all__ = [
    "StorageStrategy",
    "StorageResult",
    "MultiStorageResult",
    "CiversRestApiStorageStrategy",
    "StorageStrategyRegistry",
    "StorageManager",
]
