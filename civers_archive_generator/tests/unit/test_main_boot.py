import pytest
from unittest.mock import Mock, patch, AsyncMock
from main import ArchiveGeneratorApp
from transport_services import CliTransportService, KafkaTransportService
from configs.models import ConfigDataModel, AppConfig, TransportConfig, StorageConfig, KafkaConfig

@pytest.mark.unit
class TestMainBoot:
    """Tests for main.py application boot and transport selection."""

    @patch('main.YamlFileConfigLoader')
    @patch('main.ArchiveService')
    @pytest.mark.asyncio
    async def test_boot_cli_transport(self, mock_archive_service_class, mock_config_loader_class):
        """Test that the application boots with CliTransportService when CLI args are present."""
        # Setup mocks
        mock_config = Mock(spec=ConfigDataModel)
        mock_config.app = Mock(spec=AppConfig)
        mock_config.app.name = "test-ag"
        mock_config.app.version = "1.0.0"
        mock_config.app.get_storage_config.return_value = Mock(spec=StorageConfig)
        mock_config.app.get_storage_config.return_value.get_enabled_backends.return_value = ["local_file"]
        mock_config.domains = []
        
        mock_config_loader = Mock()
        mock_config_loader.environment = "development"
        mock_config_loader.load.return_value = mock_config
        mock_config_loader_class.return_value = mock_config_loader
        
        mock_archive_service = Mock()
        mock_archive_service_class.return_value = mock_archive_service
        
        # Instantiate application with CLI args
        app = ArchiveGeneratorApp(args=["--transport", "cli", "--url", "https://example.com"])
        
        initialized = await app.initialize()
        
        assert initialized is True
        assert isinstance(app.kafka_transport, CliTransportService)
        assert app.kafka_transport.archive_service == mock_archive_service
        assert app.kafka_transport.args == ["--transport", "cli", "--url", "https://example.com"]

    @patch('main.YamlFileConfigLoader')
    @patch('main.ArchiveService')
    @patch('transport_services.kafka.kafka_transport_service.KafkaConnectionManager')
    @patch('transport_services.kafka.kafka_transport_service.EventPublisher')
    @pytest.mark.asyncio
    async def test_boot_kafka_transport(self, mock_publisher, mock_conn_mgr, mock_archive_service_class, mock_config_loader_class):
        """Test that the application boots with KafkaTransportService when no CLI args are present."""
        # Setup mocks
        mock_config = Mock(spec=ConfigDataModel)
        mock_config.app = Mock(spec=AppConfig)
        mock_config.app.name = "test-ag"
        mock_config.app.version = "1.0.0"
        mock_config.app.get_storage_config.return_value = Mock(spec=StorageConfig)
        mock_config.app.get_storage_config.return_value.get_enabled_backends.return_value = ["local_file"]
        mock_config.domains = []
        
        # Configure Kafka transport enabled
        mock_transport = Mock(spec=TransportConfig)
        mock_transport.is_transport_enabled.return_value = True
        mock_kafka_config = Mock(spec=KafkaConfig)
        mock_kafka_config.bootstrap_servers = "localhost:9092"
        mock_kafka_config.topics = {"archive_requests": "test.requests"}
        mock_transport.kafka = mock_kafka_config
        mock_config.app.transport = mock_transport
        mock_config.app.get_kafka_config.return_value = mock_kafka_config
        
        mock_config_loader = Mock()
        mock_config_loader.environment = "development"
        mock_config_loader.load.return_value = mock_config
        mock_config_loader_class.return_value = mock_config_loader
        
        mock_archive_service = Mock()
        mock_archive_service_class.return_value = mock_archive_service
        
        # Instantiate application with no args
        app = ArchiveGeneratorApp(args=[])
        
        # Mock health check of Kafka transport to pass
        with patch.object(KafkaTransportService, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {
                'healthy': True,
                'details': {
                    'producer': 'ready',
                    'kafka_config': {'bootstrap_servers': 'localhost:9092'}
                }
            }
            initialized = await app.initialize()
            
        assert initialized is True
        assert isinstance(app.kafka_transport, KafkaTransportService)

    @patch('main.YamlFileConfigLoader')
    @patch('main.ArchiveService')
    @pytest.mark.asyncio
    async def test_boot_cli_transport_via_config(self, mock_archive_service_class, mock_config_loader_class):
        """Test that the application boots with CliTransportService when transport is enabled in config."""
        # Setup mocks
        mock_config = Mock(spec=ConfigDataModel)
        mock_config.app = Mock(spec=AppConfig)
        mock_config.app.name = "test-ag"
        mock_config.app.version = "1.0.0"
        mock_config.app.get_storage_config.return_value = Mock(spec=StorageConfig)
        mock_config.app.get_storage_config.return_value.get_enabled_backends.return_value = ["local_file"]
        mock_config.domains = []
        
        # Configure CLI transport enabled in config
        mock_transport = Mock(spec=TransportConfig)
        mock_transport.is_transport_enabled.side_effect = lambda t: t == "cli"
        mock_config.app.transport = mock_transport
        
        mock_config_loader = Mock()
        mock_config_loader.environment = "cli"
        mock_config_loader.load.return_value = mock_config
        mock_config_loader_class.return_value = mock_config_loader
        
        mock_archive_service = Mock()
        mock_archive_service_class.return_value = mock_archive_service
        
        # Instantiate application with no args (relying on config model)
        app = ArchiveGeneratorApp(args=[])
        
        initialized = await app.initialize()
        
        assert initialized is True
        assert isinstance(app.kafka_transport, CliTransportService)
