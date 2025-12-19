# tests/unit/services/test_kafka_transport_service.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from configs.models import ConfigDataModel, DomainConfig, AppConfig, KafkaConfig, TransportConfig, StorageConfig
from transport_services import KafkaTransportService
from transport_services.kafka.event_models import ArchiveRequestEvent, ArchiveStatusEvent, ArchiveCompletedEvent, ArchiveFailedEvent


@pytest.mark.unit
class TestKafkaTransportServiceInitialization:
    """Test Kafka transport service initialization"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_init_success(self, mock_producer_class, kafka_config):
        """Test successful initialization of Kafka transport service."""
        mock_producer_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        
        assert service.config == kafka_config
        assert service.kafka_config == kafka_config.app.get_kafka_config()
        assert service.topics == kafka_config.app.transport.kafka.topics
        assert service.running is False
        assert service.producer is not None
        assert service.archive_service == mock_archive_service
        
        # Verify producer was created with correct config
        mock_producer_class.assert_called_once()
        call_kwargs = mock_producer_class.call_args[1]
        assert call_kwargs['bootstrap_servers'] == "localhost:9092"
    
    def test_init_no_kafka_config(self):
        """Test initialization fails when no Kafka config is available."""
        config = ConfigDataModel(
            domains=[],
            app=AppConfig(
                name="test-app",
                version="1.0.0",
                transport=TransportConfig(enabled=["kafka"]),  # No kafka config inside transport
                storage=StorageConfig(
                    enabled=["local_file"],
                    backends={"local_file": {"base_path": "/tmp/archives"}}
                ),
                archive_directory="/tmp/archives",
                singlefile_binary_path="/usr/bin/singlefile"
            )
        )
        
        with pytest.raises(ValueError, match="Kafka configuration not found"):
            mock_archive_service = Mock()
            KafkaTransportService(config, mock_archive_service)


@pytest.mark.unit
class TestKafkaTransportServiceConfiguration:
    """Test configuration handling in Kafka transport service"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_transport_config_with_kafka(self, mock_producer_class, kafka_config):
        """Test service works with transport configuration containing Kafka config."""
        mock_producer_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        
        assert service.kafka_config.bootstrap_servers == "localhost:9092"
        assert service.kafka_config.consumer_group == "test-group"
        assert "archive_requests" in service.topics
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_new_transport_config_with_kafka(self, mock_producer_class):
        """Test service works with new transport configuration format."""
        config = ConfigDataModel(
            domains=[
                DomainConfig(name="example.com", artifacts=["warc"], webpage_types="dynamic")
            ],
            app=AppConfig(
                name="test-app",
                version="1.0.0",
                transport=TransportConfig(
                    enabled=["kafka"],
                    kafka=KafkaConfig(
                        bootstrap_servers="localhost:9092",
                        topics={"archive_requests": "test.requests"},
                        consumer_group="test-group"
                    )
                ),
                storage=StorageConfig(
                    enabled=["local_file"],
                    backends={"local_file": {"base_path": "/tmp/archives"}}
                ),
                archive_directory="/tmp/archives",
                singlefile_binary_path="/usr/bin/singlefile"
            )
        )
        
        mock_producer_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(config, mock_archive_service)
        
        assert service.kafka_config.bootstrap_servers == "localhost:9092"
        assert service.kafka_config.consumer_group == "test-group"
        assert service.topics["archive_requests"] == "test.requests"


@pytest.mark.unit
class TestKafkaTransportServiceEventHandling:
    """Test event handling in Kafka transport service"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_register_handler(self, mock_producer_class, kafka_config):
        """Test registering event handlers."""
        mock_producer_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        
        def test_handler(message, data):
            pass
        
        service.register_handler("test.topic", test_handler)
        
        assert "test.topic" in service.event_handlers
        assert service.event_handlers["test.topic"] == test_handler


@pytest.mark.unit
class TestKafkaTransportServiceLifecycle:
    """Test Kafka transport service lifecycle management"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_producer_class, kafka_config):
        """Test health check functionality."""
        mock_producer_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        service.running = True
        service.consumer = Mock()
        
        health = await service.health_check()
        
        assert health['healthy'] is True
        assert health['details']['service'] == 'kafka_transport'
        assert health['details']['running'] is True
        assert health['details']['producer_ready'] is True
        assert health['details']['consumer_ready'] is True
        assert 'kafka_config' in health['details']
