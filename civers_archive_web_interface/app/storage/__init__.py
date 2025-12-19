"""
Storage module for Civers Archive Web Interface

This module provides the extensible storage architecture with providers,
service layer, and configuration system.
"""

from .service import StorageService
from .factory import create_storage_service, create_storage_provider, StorageConfigurationError
from .providers.storage_provider_interface import StorageProviderInterface, StorageError, StorageTimeoutError, StoragePermissionError
from .providers.filesystem import FilesystemStorageProvider

__all__ = [
    "StorageService",
    "create_storage_service",
    "create_storage_provider",
    "StorageConfigurationError",
    "StorageProviderInterface",
    "StorageError",
    "StorageTimeoutError", 
    "StoragePermissionError",
    "FilesystemStorageProvider"
]