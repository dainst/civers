# tests/unit/configs/test_enhanced_config_data_model.py
import pytest

from configs.models import (
    ConfigDataModel, 
    AppConfig, 
    KafkaConfig,
    TransportConfig,
    StorageConfig
)


@pytest.mark.unit
class TestKafkaConfig:
    """Test Kafka configuration functionality"""
    
    def test_kafka_config_creation(self):
        """Test basic Kafka config creation"""
        kafka_config = KafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"requests": "test.requests"},
            consumer_group="test-group"
        )
        
        assert kafka_config.bootstrap_servers == "localhost:9092"
        assert kafka_config.topics == {"requests": "test.requests"}
        assert kafka_config.consumer_group == "test-group"
        assert kafka_config.health_check_enabled is True  # Default
        assert kafka_config.monitoring_enabled is True   # Default

    def test_kafka_config_with_monitoring_disabled(self):
        """Test Kafka config with monitoring features disabled"""
        kafka_config = KafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"requests": "test.requests"},
            consumer_group="test-group",
            health_check_enabled=False,
            monitoring_enabled=False
        )
        
        assert kafka_config.health_check_enabled is False
        assert kafka_config.monitoring_enabled is False


@pytest.mark.unit
class TestTransportConfig:
    """Test new extensible transport configuration functionality"""
    
    def test_transport_config_default(self):
        """Test transport configuration with explicit enabled list"""
        transport_config = TransportConfig(enabled=["kafka"])
        
        assert transport_config.enabled == ["kafka"]
        assert transport_config.is_transport_enabled("kafka")
        assert not transport_config.is_transport_enabled("http")
        assert transport_config.kafka is None
        assert transport_config.transports == {}
    
    def test_transport_config_with_kafka(self):
        """Test transport configuration with Kafka"""
        kafka_config = KafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"requests": "test.requests"},
            consumer_group="test-group"
        )
        
        transport_config = TransportConfig(
            enabled=["kafka"],
            kafka=kafka_config
        )
        
        assert transport_config.is_transport_enabled("kafka")
        assert not transport_config.is_transport_enabled("http")
        assert transport_config.kafka == kafka_config
    
    def test_transport_config_extensible_transports(self):
        """Test configuration with extensible transports using the generic approach"""
        transport_config = TransportConfig(
            enabled=["kafka", "http", "grpc"],
            transports={
                "http": {
                    "host": "localhost",
                    "port": 8000,
                    "ssl_enabled": False
                },
                "grpc": {
                    "host": "localhost",
                    "port": 50051,
                    "tls_enabled": False
                }
            }
        )
        
        assert transport_config.is_transport_enabled("kafka")
        assert transport_config.is_transport_enabled("http")
        assert transport_config.is_transport_enabled("grpc")
        assert not transport_config.is_transport_enabled("websocket")
        
        # Test getting transport configs
        http_config = transport_config.get_transport_config("http")
        assert http_config == {"host": "localhost", "port": 8000, "ssl_enabled": False}
        
        grpc_config = transport_config.get_transport_config("grpc")
        assert grpc_config == {"host": "localhost", "port": 50051, "tls_enabled": False}
        
        # Non-existent transport should return None
        assert transport_config.get_transport_config("websocket") is None
    
    def test_transport_config_validation_empty_enabled(self):
        """Test validation requires at least one enabled transport"""
        with pytest.raises(ValueError, match="At least one transport must be enabled"):
            TransportConfig(enabled=[])


@pytest.mark.unit
class TestStorageConfig:
    """Test extensible storage configuration functionality"""
    
    def test_storage_config_with_enabled(self):
        """Test storage configuration with enabled list"""
        storage_config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        
        assert storage_config.enabled == ["local_file"]
        assert storage_config.get_enabled_backends() == ["local_file"]
    
    def test_storage_config_custom_backends(self):
        """Test storage config with multiple backends"""
        storage_config = StorageConfig(
            enabled=["s3", "local_file"],
            backends={
                "local_file": {"base_path": "/data/archives"},
                "s3": {
                    "bucket": "my-bucket",
                    "region": "us-east-1",
                    "access_key_id": "AKIAEXAMPLE"
                },
                "gcs": {
                    "bucket": "my-gcs-bucket",
                    "project_id": "my-project"
                }
            }
        )
        
        assert storage_config.get_enabled_backends() == ["s3", "local_file"]
        
        # Test getting backend configs
        s3_config = storage_config.get_backend_config("s3")
        assert s3_config == {"bucket": "my-bucket", "region": "us-east-1", "access_key_id": "AKIAEXAMPLE"}
        
        local_config = storage_config.get_backend_config("local_file")
        assert local_config == {"base_path": "/data/archives"}
        
        gcs_config = storage_config.get_backend_config("gcs")
        assert gcs_config == {"bucket": "my-gcs-bucket", "project_id": "my-project"}
        
        # Non-existent backend should return empty dict
        assert storage_config.get_backend_config("azure") == {}


@pytest.mark.unit
class TestAppConfig:
    """Test application configuration functionality"""
    
    def test_app_config_minimal(self):
        """Test minimal app config with required transport and storage configuration"""
        transport_config = TransportConfig(enabled=["kafka"])
        storage_config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        
        app_config = AppConfig(
            name="test-app",
            version="1.0.0",
            archive_directory="/tmp/archives",
            singlefile_binary_path="/usr/bin/singlefile",
            transport=transport_config,
            storage=storage_config
        )
        
        # Should use provided transport config
        assert app_config.transport == transport_config
        assert app_config.is_transport_enabled("kafka")
        assert not app_config.is_transport_enabled("http")
        
        # Should use provided storage config
        assert app_config.get_storage_config() == storage_config
        
        # Kafka config should be None since no Kafka config provided in transport
        assert app_config.get_kafka_config() is None
    
    def test_app_config_with_transport(self):
        """Test app config with explicit transport configuration"""
        transport_config = TransportConfig(
            enabled=["kafka", "http"],
            kafka=KafkaConfig(
                bootstrap_servers="localhost:9092",
                topics={"requests": "test.requests"},
                consumer_group="test-group"
            ),
            transports={
                "http": {"host": "localhost", "port": 8000}
            }
        )
        storage_config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        
        app_config = AppConfig(
            name="test-app",
            version="1.0.0",
            archive_directory="/tmp/archives",
            singlefile_binary_path="/usr/bin/singlefile",
            transport=transport_config,
            storage=storage_config
        )
        
        # Should use provided transport config
        assert app_config.transport == transport_config
        assert app_config.is_transport_enabled("kafka")
        assert app_config.is_transport_enabled("http")
        
        # Should get Kafka config from transport
        kafka_config = app_config.get_kafka_config()
        assert kafka_config == transport_config.kafka
    
    def test_app_config_with_storage(self):
        """Test app config with storage configuration"""
        transport_config = TransportConfig(enabled=["kafka"])
        storage_config = StorageConfig(
            enabled=["s3"],
            backends={
                "s3": {"bucket": "my-bucket", "region": "us-east-1"}
            }
        )
        
        app_config = AppConfig(
            name="test-app",
            version="1.0.0",
            archive_directory="/tmp/archives",
            singlefile_binary_path="/usr/bin/singlefile",
            transport=transport_config,
            storage=storage_config
        )
        
        # Should use provided storage config
        retrieved_config = app_config.get_storage_config()
        assert retrieved_config == storage_config
        assert retrieved_config.get_enabled_backends() == ["s3"]


@pytest.mark.unit
class TestConfigDataModelIntegration:
    """Test complete configuration model integration"""
    
    def test_complete_config_minimal(self):
        """Test complete configuration with minimal settings"""
        config_data = {
            "domains": [
                {
                    "name": "example.com",
                    "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
                    "webpage_types": "dynamic"
                }
            ],
            "app": {
                "name": "archive-generator",
                "version": "1.0.0",
                "archive_directory": "/tmp/archives",
                "singlefile_binary_path": "/usr/bin/singlefile",
                "transport": {
                    "enabled": ["kafka"]
                },
                "storage": {
                    "enabled": ["local_file"],
                    "backends": {"local_file": {"base_path": "archives"}}
                }
            }
        }
        
        config = ConfigDataModel(**config_data)
        
        # Should work with minimal configuration
        assert len(config.domains) == 1
        assert config.domains[0].name == "example.com"
        assert config.app.is_transport_enabled("kafka")
        assert not config.app.is_transport_enabled("http")
    
    def test_complete_config_with_kafka(self):
        """Test complete configuration with Kafka transport"""
        config_data = {
            "domains": [
                {
                    "name": "example.com",
                    "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
                    "webpage_types": "dynamic"
                }
            ],
            "app": {
                "name": "archive-generator",
                "version": "1.0.0",
                "archive_directory": "/tmp/archives",
                "singlefile_binary_path": "/usr/bin/singlefile",
                "transport": {
                    "enabled": ["kafka"],
                    "kafka": {
                        "bootstrap_servers": "localhost:9092",
                        "topics": {"requests": "test.requests"},
                        "consumer_group": "test-group",
                        "health_check_enabled": True,
                        "monitoring_enabled": True
                    }
                },
                "storage": {
                    "enabled": ["local_file"],
                    "backends": {"local_file": {"base_path": "archives"}}
                }
            }
        }
        
        config = ConfigDataModel(**config_data)
        
        # Should work with explicit transport configuration
        assert len(config.domains) == 1
        assert config.app.is_transport_enabled("kafka")
        assert not config.app.is_transport_enabled("http")
        
        kafka_config = config.app.get_kafka_config()
        assert kafka_config.bootstrap_servers == "localhost:9092"
        assert kafka_config.health_check_enabled is True
    
    def test_complete_config_extensible_transports(self):
        """Test complete configuration with extensible transports"""
        config_data = {
            "domains": [
                {
                    "name": "example.com",
                    "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
                    "webpage_types": "dynamic"
                }
            ],
            "app": {
                "name": "archive-generator",
                "version": "1.0.0",
                "archive_directory": "/tmp/archives",
                "singlefile_binary_path": "/usr/bin/singlefile",
                "transport": {
                    "enabled": ["kafka", "http", "grpc"],
                    "kafka": {
                        "bootstrap_servers": "localhost:9092",
                        "topics": {"requests": "test.requests"},
                        "consumer_group": "test-group"
                    },
                    "transports": {
                        "http": {
                            "host": "0.0.0.0",
                            "port": 8080,
                            "ssl_enabled": False
                        },
                        "grpc": {
                            "host": "localhost",
                            "port": 50051,
                            "tls_enabled": False
                        }
                    }
                },
                "storage": {
                    "enabled": ["local_file"],
                    "backends": {"local_file": {"base_path": "archives"}}
                }
            }
        }
        
        config = ConfigDataModel(**config_data)
        
        # Should work with multiple transports
        assert config.app.is_transport_enabled("kafka")
        assert config.app.is_transport_enabled("http")
        assert config.app.is_transport_enabled("grpc")
        assert not config.app.is_transport_enabled("websocket")
        
        transport_config = config.app.transport
        http_config = transport_config.get_transport_config("http")
        assert http_config["host"] == "0.0.0.0"
        assert http_config["port"] == 8080
    
    def test_complete_config_with_storage(self):
        """Test complete configuration with storage backend"""
        config_data = {
            "domains": [
                {
                    "name": "example.com",
                    "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
                    "webpage_types": "dynamic"
                }
            ],
            "app": {
                "name": "archive-generator",
                "version": "1.0.0",
                "archive_directory": "/tmp/archives",
                "singlefile_binary_path": "/usr/bin/singlefile",
                "transport": {
                    "enabled": ["kafka"]
                },
                "storage": {
                    "enabled": ["s3", "local_file"],
                    "backends": {
                        "local_file": {"base_path": "/data/archives"},
                        "s3": {
                            "bucket": "my-archive-bucket",
                            "region": "us-east-1"
                        }
                    }
                }
            }
        }
        
        config = ConfigDataModel(**config_data)
        
        # Should work with storage configuration
        storage_config = config.app.get_storage_config()
        assert storage_config.get_enabled_backends() == ["s3", "local_file"]
        
        s3_config = storage_config.get_backend_config("s3")
        assert s3_config["bucket"] == "my-archive-bucket"
        assert s3_config["region"] == "us-east-1"
