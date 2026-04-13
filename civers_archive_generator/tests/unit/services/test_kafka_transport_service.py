# tests/unit/services/test_kafka_transport_service.py
import pytest
from unittest.mock import Mock, patch

from configs.models import ConfigDataModel, DomainConfig, AppConfig, KafkaConfig, TransportConfig, StorageConfig
from transport_services import KafkaTransportService


@pytest.mark.unit
class TestKafkaTransportServiceInitialization:
    """Test Kafka transport service initialization"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    def test_init_success(self, mock_publisher_class, mock_conn_mgr_class, kafka_config):
        """Test successful initialization of Kafka transport service."""
        mock_conn_mgr_class.return_value = Mock()
        mock_publisher_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        
        assert service.config == kafka_config
        assert service.kafka_config == kafka_config.app.get_kafka_config()
        assert service.topics == kafka_config.app.transport.kafka.topics
        assert service.running is False
        assert service.connection_manager is not None
        assert service.event_publisher is not None
        assert service.archive_service == mock_archive_service
        
        # Verify components were created with correct config
        mock_conn_mgr_class.assert_called_once_with(service.kafka_config)
        mock_publisher_class.assert_called_once_with(service.connection_manager, service.topics)
    
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
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    def test_transport_config_with_kafka(self, mock_publisher_class, mock_conn_mgr_class, kafka_config):
        """Test service works with transport configuration containing Kafka config."""
        mock_conn_mgr_class.return_value = Mock()
        mock_publisher_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        
        assert service.kafka_config.bootstrap_servers == "localhost:9092"
        assert service.kafka_config.consumer_group == "test-group"
        assert "archive_requests" in service.topics
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    def test_new_transport_config_with_kafka(self, mock_publisher_class, mock_conn_mgr_class):
        """Test service works with new transport configuration format."""
        config = ConfigDataModel(
            domains=[
                DomainConfig(name="example.com", generators=[{"name": "scoop", "artifacts": ["warc"]}], webpage_types="dynamic")
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
        
        mock_conn_mgr_class.return_value = Mock()
        mock_publisher_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(config, mock_archive_service)
        
        assert service.kafka_config.bootstrap_servers == "localhost:9092"
        assert service.kafka_config.consumer_group == "test-group"
        assert service.topics["archive_requests"] == "test.requests"


@pytest.mark.unit
class TestKafkaTransportServiceEventHandling:
    """Test event handling in Kafka transport service"""
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    def test_register_handler(self, mock_publisher_class, mock_conn_mgr_class, kafka_config):
        """Test registering event handlers."""
        mock_conn_mgr_class.return_value = Mock()
        mock_publisher_class.return_value = Mock()
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
    
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_publisher_class, mock_conn_mgr_class, kafka_config):
        """Test health check functionality."""
        mock_conn_mgr = Mock()
        mock_conn_mgr_class.return_value = mock_conn_mgr
        mock_publisher_class.return_value = Mock()
        mock_archive_service = Mock()
        
        service = KafkaTransportService(kafka_config, mock_archive_service)
        service.running = True
        
        # Test healthy state
        mock_conn_mgr.producer = Mock()
        mock_conn_mgr.consumer = Mock()
        
        health = await service.health_check()
        
        assert health['healthy'] is True
        assert health['service_name'] == 'KafkaTransportService'
        assert health['details']['running'] is True
        assert health['details']['producer'] == 'ready'
        assert health['details']['consumer'] == 'ready'

from unittest.mock import AsyncMock

@pytest.mark.unit
class TestKafkaTransportServiceEventProcessing:
    """Test core event processing logic in Kafka transport service"""
    
    @pytest.mark.asyncio
    async def test_handle_archive_request_success(self, kafka_config):
        """Test successful archive request handling."""
        mock_archive_service = AsyncMock()
        service = KafkaTransportService(kafka_config, mock_archive_service)
        service.event_publisher = AsyncMock()
        
        # Mock ArchiveService result
        mock_archive_service.create_archive.return_value = {
            'success': True,
            'request_id': 'req-123',
            'url': 'https://example.com',
            'archive_path': '/tmp/archives/req-123',
            'artifacts_created': ['warc', 'screenshot'],
            'processing_time_seconds': 5.0,
            'domain_config': {
                'name': 'example.com',
                'generators': [{'name': 'scoop', 'artifacts': ['warc']}]
            }
        }
        
        # Test data
        data = {
            'request_id': 'req-123',
            'url': 'https://example.com',
            'priority': 1
        }
        
        await service._handle_archive_request(None, data)
        
        # Verify archive service was called
        mock_archive_service.create_archive.assert_called_once_with(
            'https://example.com', 'req-123', 1
        )
        
        # Verify events were published
        assert service.event_publisher.publish_status_update.call_count == 2
        service.event_publisher.publish_archive_completed.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_archive_request_failure(self, kafka_config):
        """Test archive request handling on failure."""
        mock_archive_service = AsyncMock()
        service = KafkaTransportService(kafka_config, mock_archive_service)
        service.event_publisher = AsyncMock()
        
        # Mock ArchiveService result
        mock_archive_service.create_archive.return_value = {
            'success': False,
            'request_id': 'req-123',
            'url': 'https://example.com',
            'error': 'Domain not allowed',
            'error_type': 'domain_not_allowed'
        }
        
        # Test data
        data = {
            'request_id': 'req-123',
            'url': 'https://example.com',
            'priority': 1
        }
        
        await service._handle_archive_request(None, data)
        
        # Verify archive service was called
        mock_archive_service.create_archive.assert_called_once()
        
        # Verify failure event was published
        service.event_publisher.publish_archive_failed.assert_called_once()
        assert service.event_publisher.publish_status_update.call_count == 2
