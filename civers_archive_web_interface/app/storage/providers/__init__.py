"""
Storage providers package for the Civers Archive Web Interface.

This package contains the storage provider implementations for different
storage backends (filesystem, S3, database, etc.).
"""

from .storage_provider_interface import StorageProviderInterface
from .filesystem import FilesystemStorageProvider

__all__ = [
    "StorageProviderInterface",
    "FilesystemStorageProvider",
]