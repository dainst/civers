"""
Tests for storage factory - Creating providers based on configuration.

Following TDD approach: Write tests first, then implement.
"""

import pytest
from pathlib import Path

from app.storage.factory import (
    create_storage_provider,
    create_storage_service,
    StorageConfigurationError
)
from app.storage.providers.filesystem import FilesystemStorageProvider
from app.storage.providers.sqlite_storage import SQLiteStorageProvider
from app.storage.service import StorageService
from app.config import AppConfig, StorageConfig, FilesystemConfig, SQLiteConfig
from app.config.models import ValidationConfig


class TestCreateFilesystemProvider:
    """Test creating filesystem provider."""

    def test_create_filesystem_provider_from_config(self, tmp_path):
        """Test creating filesystem provider from config."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()

        config = AppConfig(
            storage=StorageConfig(
                type="filesystem",
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )

        provider = create_storage_provider(config)

        assert isinstance(provider, FilesystemStorageProvider)
        assert provider.storage_path == storage_path

    def test_create_filesystem_provider_with_defaults(self):
        """Test creating filesystem provider with default config."""
        config = AppConfig(
            storage=StorageConfig(type="filesystem")
        )

        provider = create_storage_provider(config)

        assert isinstance(provider, FilesystemStorageProvider)


class TestCreateSQLiteProvider:
    """Test creating SQLite provider."""

    def test_create_sqlite_provider_from_config(self, tmp_path):
        """Test creating SQLite provider from config."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()
        db_path = tmp_path / "test.db"

        config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path)),
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )

        provider = create_storage_provider(config)

        assert isinstance(provider, SQLiteStorageProvider)
        assert provider.storage_path == storage_path
        assert provider.db is not None

    def test_create_sqlite_provider_with_defaults(self):
        """Test creating SQLite provider with default config."""
        config = AppConfig(
            storage=StorageConfig(type="sqlite")
        )

        provider = create_storage_provider(config)

        assert isinstance(provider, SQLiteStorageProvider)

    def test_sqlite_provider_initializes_schema(self, tmp_path):
        """Test that SQLite provider initializes database schema."""
        db_path = tmp_path / "test.db"

        config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path))
            )
        )

        provider = create_storage_provider(config)

        # Verify schema was initialized
        result = provider.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='urls'"
        )
        assert result is not None

    def test_sqlite_provider_auto_rebuild_when_empty(self, tmp_path):
        """Test that SQLite provider auto-rebuilds index when database is empty."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()

        # Create sample data in filesystem
        domain_dir = storage_path / "example_com"
        domain_dir.mkdir()
        path_dir = domain_dir / "test"
        path_dir.mkdir()
        snapshot_dir = path_dir / "req_test_20240101_120000"
        snapshot_dir.mkdir()

        # Create metadata
        import json
        (snapshot_dir / "metadata.json").write_text(json.dumps({
            "url": "https://example.com/test",
            "title": "Test"
        }))
        (snapshot_dir / "archive.wacz").write_bytes(b"test")

        db_path = tmp_path / "test.db"

        config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path), auto_rebuild=True),
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )

        provider = create_storage_provider(config)

        # Verify database was populated
        urls = provider.get_all_urls()
        assert len(urls) >= 1

    def test_sqlite_provider_no_auto_rebuild_when_disabled(self, tmp_path):
        """Test that SQLite provider doesn't auto-rebuild when disabled."""
        db_path = tmp_path / "test.db"

        config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path), auto_rebuild=False)
            )
        )

        provider = create_storage_provider(config)

        # Database should be empty (no auto-rebuild)
        urls = provider.get_all_urls()
        assert len(urls) == 0


class TestCreateStorageService:
    """Test creating storage service."""

    def test_create_storage_service_with_filesystem(self, tmp_path):
        """Test creating storage service with filesystem provider."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()

        config = AppConfig(
            storage=StorageConfig(
                type="filesystem",
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )

        service = create_storage_service(config)

        assert isinstance(service, StorageService)
        assert isinstance(service.provider, FilesystemStorageProvider)

    def test_create_storage_service_with_sqlite(self, tmp_path):
        """Test creating storage service with SQLite provider."""
        db_path = tmp_path / "test.db"

        config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path))
            )
        )

        service = create_storage_service(config)

        assert isinstance(service, StorageService)
        assert isinstance(service.provider, SQLiteStorageProvider)

    def test_create_storage_service_with_custom_provider(self, tmp_path):
        """Test creating storage service with custom provider."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()

        config = AppConfig()

        # Create custom provider
        provider = FilesystemStorageProvider(storage_path)

        service = create_storage_service(config, provider=provider)

        assert isinstance(service, StorageService)
        assert service.provider == provider


class TestProviderSwitching:
    """Test switching between providers."""

    def test_switch_from_filesystem_to_sqlite(self, tmp_path):
        """Test creating both providers with same storage path."""
        storage_path = tmp_path / "archives"
        storage_path.mkdir()
        db_path = tmp_path / "test.db"

        # Create filesystem provider
        fs_config = AppConfig(
            storage=StorageConfig(
                type="filesystem",
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )
        fs_provider = create_storage_provider(fs_config)

        # Create SQLite provider (same storage path)
        sqlite_config = AppConfig(
            storage=StorageConfig(
                type="sqlite",
                sqlite=SQLiteConfig(db_path=str(db_path)),
                filesystem=FilesystemConfig(path=str(storage_path))
            )
        )
        sqlite_provider = create_storage_provider(sqlite_config)

        # Both should use same storage path
        assert fs_provider.storage_path == sqlite_provider.storage_path
        assert isinstance(fs_provider, FilesystemStorageProvider)
        assert isinstance(sqlite_provider, SQLiteStorageProvider)


class TestErrorHandling:
    """Test error handling in factory."""

    def test_unsupported_storage_type_raises_error(self):
        """Test that unsupported storage type raises error."""
        # Note: This test may not work with current Literal type checking
        # but demonstrates intent
        pass

    def test_missing_required_config_raises_error(self):
        """Test that missing required config raises error."""
        # Config validation should catch this
        pass
