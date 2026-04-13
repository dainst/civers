"""
Storage Layer Package.

Provides pluggable storage backends for metadata persistence.
"""

from .civers_rest_api_storage_strategy import CiversRestApiStorageStrategy
from .local_file_storage_strategy import LocalFileStorageStrategy
from .storage_manager import StorageManager
from .storage_strategy import MultiStorageResult, StorageResult, StorageStrategy
from .strategy_registry import StorageStrategyRegistry

# Register built-in storage strategies
StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)

# Future strategies can be registered here or via plugins:
# StorageStrategyRegistry.register("s3", S3StorageStrategy)
# StorageStrategyRegistry.register("azure_blob", AzureBlobStorageStrategy)

__all__ = [
    "StorageStrategy",
    "StorageResult",
    "MultiStorageResult",
    "LocalFileStorageStrategy",
    "CiversRestApiStorageStrategy",
    "StorageStrategyRegistry",
    "StorageManager",
]
