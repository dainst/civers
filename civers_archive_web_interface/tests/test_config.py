"""
Unit tests for the configuration system.
"""

import os
import tempfile
import pytest
import yaml
from pathlib import Path
from pydantic import ValidationError

from app.config import load_app_config, AppConfig, StorageConfig, FilesystemConfig, SQLiteConfig, CacheConfig, ConfigurationError


class TestConfigurationModels:
    """Test configuration Pydantic models."""

    def test_filesystem_config_defaults(self):
        """Test FilesystemConfig with default values."""
        config = FilesystemConfig()
        assert config.path == "archives"
        assert config.timeout_seconds == 10

    def test_filesystem_config_custom(self):
        """Test FilesystemConfig with custom values."""
        config = FilesystemConfig(path="/custom/path", timeout_seconds=30)
        assert config.path == "/custom/path"
        assert config.timeout_seconds == 30

    def test_filesystem_config_validation(self):
        """Test FilesystemConfig validation."""
        # Valid config
        config = FilesystemConfig(timeout_seconds=0)
        assert config.timeout_seconds == 0

        # Invalid timeout
        with pytest.raises(ValidationError):
            FilesystemConfig(timeout_seconds=-1)

    def test_sqlite_config_defaults(self):
        """Test SQLiteConfig with default values."""
        config = SQLiteConfig()
        assert config.db_path == "data/archives.db"
        assert config.auto_rebuild is True
        assert config.connection_timeout == 10

    def test_sqlite_config_custom(self):
        """Test SQLiteConfig with custom values."""
        config = SQLiteConfig(
            db_path="/custom/path/db.sqlite",
            auto_rebuild=False,
            connection_timeout=30
        )
        assert config.db_path == "/custom/path/db.sqlite"
        assert config.auto_rebuild is False
        assert config.connection_timeout == 30

    def test_sqlite_config_validation(self):
        """Test SQLiteConfig validation."""
        # Valid config with minimum timeout
        config = SQLiteConfig(connection_timeout=1)
        assert config.connection_timeout == 1

        # Invalid timeout (less than 1)
        with pytest.raises(ValidationError):
            SQLiteConfig(connection_timeout=0)

        with pytest.raises(ValidationError):
            SQLiteConfig(connection_timeout=-1)

    def test_cache_config_defaults(self):
        """Test CacheConfig with default values."""
        config = CacheConfig()
        assert config.ttl_seconds == 60
        assert config.max_entries == 1000

    def test_cache_config_validation(self):
        """Test CacheConfig validation."""
        
        # Invalid TTL
        with pytest.raises(ValidationError):
            CacheConfig(ttl_seconds=0)

    def test_storage_config_defaults(self):
        """Test StorageConfig with default values."""
        config = StorageConfig()
        assert config.type == "filesystem"
        assert config.filesystem is not None
        assert isinstance(config.filesystem, FilesystemConfig)
        assert isinstance(config.cache, CacheConfig)

    def test_storage_config_filesystem_validation(self):
        """Test StorageConfig filesystem provider validation."""
        # Default filesystem config should be created
        config = StorageConfig(type="filesystem")
        assert config.filesystem is not None
        assert config.filesystem.path == "archives"

    def test_storage_config_sqlite_defaults(self):
        """Test StorageConfig SQLite provider with defaults."""
        # Default SQLite config should be created
        config = StorageConfig(type="sqlite")
        assert config.type == "sqlite"
        assert config.sqlite is not None
        assert isinstance(config.sqlite, SQLiteConfig)
        assert config.sqlite.db_path == "data/archives.db"
        assert config.sqlite.auto_rebuild is True
        # SQLite provider also needs filesystem config for file storage
        assert config.filesystem is not None

    def test_storage_config_sqlite_custom(self):
        """Test StorageConfig SQLite provider with custom values."""
        config = StorageConfig(
            type="sqlite",
            sqlite=SQLiteConfig(
                db_path="/custom/db.sqlite",
                auto_rebuild=False,
                connection_timeout=20
            ),
            filesystem=FilesystemConfig(path="/custom/archives")
        )
        assert config.type == "sqlite"
        assert config.sqlite.db_path == "/custom/db.sqlite"
        assert config.sqlite.auto_rebuild is False
        assert config.sqlite.connection_timeout == 20
        assert config.filesystem.path == "/custom/archives"

    def test_storage_config_sqlite_validation(self):
        """Test StorageConfig SQLite provider validation."""
        # SQLite config should be created if not provided
        config = StorageConfig(type="sqlite")
        assert config.sqlite is not None
        assert config.filesystem is not None

    def test_storage_config_s3_validation(self):
        """Test StorageConfig S3 provider validation."""
        # S3 config required when type is s3
        with pytest.raises(ValidationError):
            StorageConfig(type="s3")

    def test_storage_config_database_validation(self):
        """Test StorageConfig database provider validation."""
        # Database config required when type is database
        with pytest.raises(ValidationError):
            StorageConfig(type="database")

    def test_app_config_defaults(self):
        """Test AppConfig with default values."""
        config = AppConfig()
        assert isinstance(config.storage, StorageConfig)
        assert config.storage.type == "filesystem"


class TestConfigurationLoader:
    """Test configuration loading functionality."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "storage": {
                    "type": "filesystem",
                    "filesystem": {
                        "path": "test_archives",
                        "timeout_seconds": 20
                    },
                    "cache": {
                        "ttl_seconds": 300
                    }
                }
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        
        yield temp_path
        temp_path.unlink()

    def test_load_valid_config(self, temp_config_file):
        """Test loading valid configuration file."""
        config = load_app_config(temp_config_file)
        
        assert isinstance(config, AppConfig)
        assert config.storage.type == "filesystem"
        assert config.storage.filesystem.path == "test_archives"
        assert config.storage.filesystem.timeout_seconds == 20
        assert config.storage.cache.ttl_seconds == 300

    def test_load_config_missing_file(self):
        """Test loading non-existent configuration file."""
        missing_path = Path("/nonexistent/config.yaml")
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_app_config(missing_path)
        assert "Configuration file not found" in str(exc_info.value)

    def test_load_config_empty_file(self):
        """Test loading empty configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ConfigurationError) as exc_info:
                load_app_config(temp_path)
            assert "Configuration file is empty" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ConfigurationError) as exc_info:
                load_app_config(temp_path)
            assert "YAML parsing error" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_environment_overrides(self, temp_config_file, monkeypatch):
        """Test environment variable overrides."""
        # Set environment variables
        monkeypatch.setenv("CIVERS_STORAGE_TYPE", "filesystem")
        monkeypatch.setenv("CIVERS_FILESYSTEM_PATH", "/override/path")
        monkeypatch.setenv("CIVERS_FILESYSTEM_TIMEOUT_SECONDS", "45")
        monkeypatch.setenv("CIVERS_CACHE_TTL_SECONDS", "600")
        
        config = load_app_config(temp_config_file)
        
        assert config.storage.type == "filesystem"
        assert config.storage.filesystem.path == "/override/path"
        assert config.storage.filesystem.timeout_seconds == 45
        assert config.storage.cache.ttl_seconds == 600

    def test_legacy_environment_precedence(self, temp_config_file, monkeypatch):
        """Test that new env vars take precedence over legacy ones."""
        monkeypatch.setenv("SCANNER_CACHE_TTL", "180")
        monkeypatch.setenv("CIVERS_CACHE_TTL_SECONDS", "240")
        
        config = load_app_config(temp_config_file)
        
        # New env var should take precedence
        assert config.storage.cache.ttl_seconds == 240

    def test_minimal_config_with_defaults(self):
        """Test loading minimal config with defaults applied."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "storage": {
                    "type": "filesystem"
                }
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        
        try:
            config = load_app_config(temp_path)
            
            # Defaults should be applied
            assert config.storage.type == "filesystem"
            assert config.storage.filesystem.path == "archives"
            assert config.storage.filesystem.timeout_seconds == 10
            assert config.storage.cache.ttl_seconds == 60
        finally:
            temp_path.unlink()

    def test_default_config_path(self):
        """Test using default config path when none provided."""
        # If config/storage.yaml exists, it should load successfully
        # If it doesn't exist, it should raise ConfigurationError
        try:
            config = load_app_config()
            # If successful, verify it's a valid config
            assert isinstance(config, AppConfig)
            assert isinstance(config.storage, StorageConfig)
        except ConfigurationError as e:
            # If it fails, it should mention the default path
            assert "config/storage.yaml" in str(e) or "Configuration file not found" in str(e)