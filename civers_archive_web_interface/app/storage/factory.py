"""
Storage factory for creating storage providers and services.

This module provides factory functions for creating storage providers
and services based on configuration.
"""

import logging
from pathlib import Path
from typing import Optional

from ..config import StorageConfig, AppConfig
from .providers.storage_provider_interface import StorageProviderInterface
from .providers.filesystem import FilesystemStorageProvider
from .providers.sqlite_storage import SQLiteStorageProvider
from .service import StorageService
from ..database.sqlite_manager import SQLiteManager
from ..database.models import get_schema_sql
from ..database.indexer import FilesystemIndexer

logger = logging.getLogger(__name__)


class StorageConfigurationError(Exception):
    """Exception raised for storage configuration errors."""
    pass


def create_storage_provider(app_config: AppConfig) -> StorageProviderInterface:
    """
    Create storage provider based on configuration.
    
    Args:
        app_config: Full application configuration object
        
    Returns:
        StorageProvider instance
        
    Raises:
        StorageConfigurationError: If provider creation fails
    """
    try:
        config = app_config.storage
        if config.type == 'filesystem':
            return _create_filesystem_provider(config, app_config.validation)
        elif config.type == 'sqlite':
            return _create_sqlite_provider(config, app_config.validation)
        # elif config.type == 's3': # Possible future implementation
        #     raise StorageConfigurationError("S3 storage provider not yet implemented")
        else:
            raise StorageConfigurationError(f"Unknown storage provider type: {config.type}")

    except Exception as e:
        raise StorageConfigurationError(f"Provider creation failed: {e}") from e


def _create_filesystem_provider(config: StorageConfig, validation_config) -> FilesystemStorageProvider:
    """
    Create filesystem storage provider.
    
    Args:
        config: Storage configuration object
        validation_config: Validation configuration object
        
    Returns:
        FilesystemStorageProvider instance
    """
    fs_config = config.filesystem
    if fs_config is None:
        raise StorageConfigurationError("Filesystem configuration is required")
    
    # Get storage path
    storage_path = Path(fs_config.path)
    if not storage_path.is_absolute():
        # Make relative paths relative to project root
        storage_path = Path.cwd() / storage_path
    
    logger.debug(f"Creating filesystem storage provider: path={storage_path}, timeout={fs_config.timeout_seconds}s")
    
    return FilesystemStorageProvider(storage_path, fs_config.timeout_seconds, validation_config)


def _create_sqlite_provider(config: StorageConfig, validation_config) -> SQLiteStorageProvider:
    """
    Create SQLite storage provider.

    Args:
        config: Storage configuration object
        validation_config: Validation configuration object

    Returns:
        SQLiteStorageProvider instance
    """
    sqlite_config = config.sqlite
    if sqlite_config is None:
        raise StorageConfigurationError("SQLite configuration is required")

    fs_config = config.filesystem
    if fs_config is None:
        raise StorageConfigurationError("Filesystem configuration is required for SQLite provider")

    # Get storage path
    storage_path = Path(fs_config.path)
    if not storage_path.is_absolute():
        # Make relative paths relative to project root
        storage_path = Path.cwd() / storage_path

    # Get database path
    db_path = Path(sqlite_config.db_path)
    if not db_path.is_absolute():
        # Make relative paths relative to project root
        db_path = Path.cwd() / db_path

    logger.debug(f"Creating SQLite storage provider: db={db_path}, storage={storage_path}")

    # Create database manager
    db_manager = SQLiteManager(db_path)
    db_manager.connect()

    # Initialize schema
    db_manager.initialize_schema(get_schema_sql())
    logger.debug("Database schema initialized")

    # Check if database needs indexing
    cursor = db_manager.execute_query("SELECT COUNT(*) as count FROM urls")
    result = cursor.fetchone()
    url_count = result[0] if result else 0

    # if url_count == 0 and sqlite_config.auto_rebuild:
    #     logger.info("Database empty, rebuilding index from filesystem")
    #     # Create temporary filesystem provider for indexing
    #     fs_provider = FilesystemStorageProvider(storage_path, validation_config=validation_config)
    #     indexer = FilesystemIndexer(db_manager, fs_provider)
    #     stats = indexer.rebuild_index()
    #     logger.info(f"Index rebuilt: {stats}")
    
    logger.info("rebuilding index from filesystem")
    # Create temporary filesystem provider for indexing
    fs_provider = FilesystemStorageProvider(storage_path, validation_config=validation_config)
    indexer = FilesystemIndexer(db_manager, fs_provider)
    stats = indexer.rebuild_index()
    logger.info(f"Index rebuilt: {stats}")

    # Create SQLite provider
    return SQLiteStorageProvider(db_manager, storage_path, validation_config)


def create_storage_service(app_config: AppConfig, provider: Optional[StorageProviderInterface] = None) -> StorageService:
    """
    Create storage service with provider and caching.
    
    Args:
        app_config: Full application configuration object
        provider: Optional storage provider (will be created if not provided)
        
    Returns:
        StorageService instance
        
    Raises:
        StorageConfigurationError: If service creation fails
    """
    try:
        # Create provider if not provided
        if provider is None:
            provider = create_storage_provider(app_config)
        
        config = app_config.storage
        logger.debug(f"Creating storage service with cache TTL: {config.cache.ttl_seconds}s")
        
        return StorageService(provider, config.cache.ttl_seconds)
        
    except Exception as e:
        raise StorageConfigurationError(f"Service creation failed: {e}") from e


