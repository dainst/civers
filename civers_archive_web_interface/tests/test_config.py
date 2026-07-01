"""
Unit tests for the configuration system.
"""

import pytest
from pydantic import ValidationError

from configs import (
    YamlFileConfigLoader,
    AppConfig,
    StorageConfig,
    FilesystemConfig,
    SQLiteConfig,
    CacheConfig,
    DomainConfig,
    KafkaConfig,
    TransportConfig,
)


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

    def test_domain_config_properties(self):
        """Test DomainConfig properties and validators inherited/added."""
        domain = DomainConfig(name="example.com", enabled=True, description="Test domain")
        assert domain.display_name == "example.com - Test domain"
        assert domain.is_wildcard is False
        assert domain.is_default is False

        wildcard = DomainConfig(name="*.example.com")
        assert wildcard.is_wildcard is True

        default_domain = DomainConfig(name="default")
        assert default_domain.is_default is True

    def test_kafka_config_custom(self):
        """Test KafkaConfig behavior."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            topics={"orchestrator_requests": "test.requests"}
        )
        assert config.bootstrap_servers == "kafka:9092"
        assert config.get_topic("orchestrator_requests") == "test.requests"

    def test_transport_config_custom(self):
        """Test TransportConfig properties."""
        kafka_config = KafkaConfig(bootstrap_servers="kafka:9092", topics={"orchestrator_requests": "test.requests"})
        transport = TransportConfig(enabled=["kafka"], kafka=kafka_config)
        assert transport.kafka_enabled is True
        assert transport.is_transport_enabled("kafka") is True


class TestConfigurationLoader:
    """Test configuration loading functionality."""

    def test_minimal_config_with_defaults(self):
        """Test that loading configuration loads default directories correctly."""
        loader = YamlFileConfigLoader()
        config = loader.load()
        assert config.app.name == "Civers Archive Web Interface"
        assert config.directories.templates == "templates"
        assert config.directories.static == "static"