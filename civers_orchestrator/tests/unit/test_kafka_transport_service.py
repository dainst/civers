# tests/unit/test_kafka_transport_service.py
"""Unit tests for Kafka Transport Service.

Following TDD approach - these tests define the expected behavior
of the KafkaTransportService before implementation.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from configs.models import ConfigDataModel, AppConfig, TransportConfig, KafkaConfig
from configs.models import KafkaConsumerConfig, KafkaProducerConfig, KafkaTopicsConfig, KafkaComponentMapping
from transport_services.transport_service_interface import TransportServiceInterface


@pytest.fixture
def minimal_kafka_config():
    """Create minimal Kafka configuration for testing."""
    return ConfigDataModel(
        app=AppConfig(
            name="test-orchestrator",
            version="1.0.0",
            environment="testing"
        ),
        transport=TransportConfig(
            enabled=["kafka"],
            kafka=KafkaConfig(
                bootstrap_servers="localhost:29092",
                consumer=KafkaConsumerConfig(
                    group_id="test-orchestrator-group",
                    auto_offset_reset="earliest"
                ),
                producer=KafkaProducerConfig(
                    acks="all",
                    retries=3
                ),
                topics=KafkaTopicsConfig(
                    orchestrator_requests="test.orchestrator.requests",
                    orchestrator_status="test.orchestrator.status",
                    orchestrator_completed="test.orchestrator.completed",
                    orchestrator_failed="test.orchestrator.failed"
                ),
                component_mappings={
                    "archive_generator": KafkaComponentMapping(
                        request_topic="archive.requests",
                        response_topics={
                            "success": "archive.completed",
                            "failure": "archive.failed"
                        },
                        event_models={
                            "request": "ArchiveRequestEvent",
                            "success": "ArchiveCompletedEvent",
                            "failure": "ArchiveFailedEvent"
                        }
                    ),
                    "metadata_extractor": KafkaComponentMapping(
                        request_topic="metadata.requests",
                        response_topics={
                            "success": "metadata.completed",
                            "failure": "metadata.failed"
                        },
                        event_models={
                            "request": "MetadataExtractionRequestEvent",
                            "success": "MetadataExtractionCompletedEvent",
                            "failure": "MetadataExtractionFailedEvent"
                        }
                    )
                }
            )
        ),
        domains=[],
        workflows=[]
    )


@pytest.mark.unit
class TestKafkaTransportServiceInitialization:
    """Test Kafka transport service initialization."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_init_success(self, mock_producer_class, minimal_kafka_config):
        """Test successful initialization of Kafka transport service."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Verify basic attributes
        assert service.config == minimal_kafka_config
        assert service.kafka_config == minimal_kafka_config.transport.kafka
        assert service.topics == minimal_kafka_config.transport.kafka.topics
        assert service.running is False
        assert service.producer is not None
        assert service.orchestrator == mock_orchestrator_service
        assert service.adapter is not None  # NEW: Adapter should be initialized

        # Verify producer was created with correct config
        mock_producer_class.assert_called_once()
        call_kwargs = mock_producer_class.call_args[1]
        assert call_kwargs['bootstrap_servers'] == "localhost:29092"
        assert call_kwargs['acks'] == 1  # From implementation
        assert call_kwargs['retries'] == 3

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_init_creates_empty_event_handlers(self, mock_producer_class, minimal_kafka_config):
        """Test that event_handlers dict is initialized empty."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        assert isinstance(service.event_handlers, dict)
        assert len(service.event_handlers) == 0

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_init_consumer_is_none(self, mock_producer_class, minimal_kafka_config):
        """Test that consumer is not initialized in __init__ (only on start)."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        assert service.consumer is None

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_init_producer_failure(self, mock_producer_class, minimal_kafka_config):
        """Test initialization fails gracefully when producer creation fails."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.side_effect = Exception("Kafka connection failed")
        mock_orchestrator_service = Mock()

        with pytest.raises(Exception, match="Kafka connection failed"):
            KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)


@pytest.mark.unit
class TestKafkaTransportServiceInterface:
    """Test that KafkaTransportService implements TransportServiceInterface."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_implements_transport_service_interface(self, mock_producer_class, minimal_kafka_config):
        """Test that KafkaTransportService is a subclass of TransportServiceInterface."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        assert isinstance(service, TransportServiceInterface)

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_has_required_methods(self, mock_producer_class, minimal_kafka_config):
        """Test that service has all required interface methods."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Check all required methods from TransportServiceInterface
        assert hasattr(service, 'start')
        assert hasattr(service, 'stop')
        assert hasattr(service, 'register_handler')
        assert hasattr(service, 'health_check')
        assert hasattr(service, 'send_response')
        assert hasattr(service, 'get_transport_info')


@pytest.mark.unit
class TestKafkaTransportServiceConfiguration:
    """Test configuration handling in Kafka transport service."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_kafka_config_extraction(self, mock_producer_class, minimal_kafka_config):
        """Test that Kafka config is correctly extracted from ConfigDataModel."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        assert service.kafka_config.bootstrap_servers == "localhost:29092"
        assert service.kafka_config.consumer.group_id == "test-orchestrator-group"
        assert service.kafka_config.producer.acks == "all"
        assert service.kafka_config.producer.retries == 3

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_topics_configuration(self, mock_producer_class, minimal_kafka_config):
        """Test that topic names are correctly loaded from config."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        assert service.topics.orchestrator_requests == "test.orchestrator.requests"
        assert service.topics.orchestrator_status == "test.orchestrator.status"
        assert service.topics.orchestrator_completed == "test.orchestrator.completed"
        assert service.topics.orchestrator_failed == "test.orchestrator.failed"


@pytest.mark.unit
class TestKafkaTransportServiceEventHandling:
    """Test event handler registration."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_register_handler(self, mock_producer_class, minimal_kafka_config):
        """Test registering event handlers for topics."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        def test_handler(message, data):
            pass

        service.register_handler("test.topic", test_handler)

        assert "test.topic" in service.event_handlers
        assert service.event_handlers["test.topic"] == test_handler

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_register_multiple_handlers(self, mock_producer_class, minimal_kafka_config):
        """Test registering multiple handlers for different topics."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        def handler1(message, data):
            pass

        def handler2(message, data):
            pass

        service.register_handler("topic1", handler1)
        service.register_handler("topic2", handler2)

        assert len(service.event_handlers) == 2
        assert service.event_handlers["topic1"] == handler1
        assert service.event_handlers["topic2"] == handler2


@pytest.mark.unit
class TestKafkaTransportServiceGetTransportInfo:
    """Test get_transport_info method."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_get_transport_info_structure(self, mock_producer_class, minimal_kafka_config):
        """Test that get_transport_info returns correct structure."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        info = service.get_transport_info()

        assert isinstance(info, dict)
        assert 'transport_type' in info
        assert info['transport_type'] == 'KafkaTransportService'
        assert 'kafka_config' in info
        assert 'status' in info
        # capabilities is optional - not checking for it

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_get_transport_info_kafka_config(self, mock_producer_class, minimal_kafka_config):
        """Test that kafka_config is included in transport info."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        info = service.get_transport_info()

        kafka_config = info['kafka_config']
        assert kafka_config['bootstrap_servers'] == "localhost:29092"
        assert kafka_config['consumer_group'] == "test-orchestrator-group"
        # topics is no longer in kafka_config - moved to component_mappings

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_get_transport_info_status(self, mock_producer_class, minimal_kafka_config):
        """Test that status information is included."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        info = service.get_transport_info()

        status = info['status']
        assert 'running' in status
        assert 'producer_ready' in status
        assert 'consumer_ready' in status
        assert status['running'] is False  # Not started yet
        assert status['producer_ready'] is True  # Producer created in __init__
        assert status['consumer_ready'] is False  # Consumer not created yet


@pytest.mark.unit
class TestSafeJsonDeserializer:
    """Test the _safe_json_deserializer static method."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_deserialize_valid_json(self, mock_producer_class, minimal_kafka_config):
        """Test deserializing valid JSON bytes."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        json_bytes = b'{"request_id": "123", "url": "https://example.com"}'
        result = service._safe_json_deserializer(json_bytes)

        assert result is not None
        assert isinstance(result, dict)
        assert result['request_id'] == "123"
        assert result['url'] == "https://example.com"

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_deserialize_none(self, mock_producer_class, minimal_kafka_config):
        """Test deserializing None returns None."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        result = service._safe_json_deserializer(None)

        assert result is None

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_deserialize_invalid_json(self, mock_producer_class, minimal_kafka_config):
        """Test deserializing invalid JSON returns None with warning."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        invalid_bytes = b'not json at all'
        result = service._safe_json_deserializer(invalid_bytes)

        assert result is None

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    def test_deserialize_json_with_extra_text(self, mock_producer_class, minimal_kafka_config):
        """Test extracting JSON from bytes with extra text."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # JSON embedded in other text
        bytes_with_extra = b'Some prefix {"request_id": "123"} some suffix'
        result = service._safe_json_deserializer(bytes_with_extra)

        # Should extract the JSON object
        assert result is not None
        assert isinstance(result, dict)
        assert result['request_id'] == "123"


@pytest.mark.unit
class TestKafkaTransportServiceStart:
    """Test starting the Kafka transport service."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @patch('transport_services.kafka.kafka_transport_service.KafkaConsumer')
    @pytest.mark.asyncio
    async def test_start_registers_default_handler(self, mock_consumer_class, mock_producer_class, minimal_kafka_config):
        """Test that start() registers handler for orchestrator.requests topic."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_consumer_instance = Mock()
        mock_consumer_class.return_value = mock_consumer_instance
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Mock the consuming loop to avoid blocking
        service._start_consuming = AsyncMock()

        await service.start()

        # Verify handler was registered for orchestrator.requests
        assert "test.orchestrator.requests" in service.event_handlers
        assert service.running is True

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @patch('transport_services.kafka.kafka_transport_service.KafkaConsumer')
    @pytest.mark.asyncio
    async def test_start_creates_consumer(self, mock_consumer_class, mock_producer_class, minimal_kafka_config):
        """Test that start() creates Kafka consumer."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_consumer_instance = Mock()
        mock_consumer_class.return_value = mock_consumer_instance
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)
        service._start_consuming = AsyncMock()

        await service.start()

        # Verify consumer was created
        assert service.consumer is not None
        mock_consumer_class.assert_called_once()

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_start_failure_stops_service(self, mock_producer_class, minimal_kafka_config):
        """Test that start() failure triggers cleanup."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Mock _setup_consumer to raise exception
        service._setup_consumer = Mock(side_effect=Exception("Consumer setup failed"))
        service.stop = AsyncMock()

        with pytest.raises(Exception, match="Consumer setup failed"):
            await service.start()

        # Verify stop was called for cleanup
        service.stop.assert_called_once()


@pytest.mark.unit
class TestKafkaTransportServiceMessageProcessing:
    """Test message processing and routing."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_process_kafka_message_routes_to_handler(self, mock_producer_class, minimal_kafka_config):
        """Test that _process_kafka_message routes to registered handler."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.key = "test-request-123"
        mock_message.value = {"request_id": "test-request-123", "url": "https://example.com"}

        # Register a handler
        mock_handler = AsyncMock()
        service.register_handler("test.topic", mock_handler)

        # Process the message
        await service._process_kafka_message(mock_message)

        # Verify handler was called with message and data
        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[0] == mock_message
        assert call_args[1] == mock_message.value

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_process_kafka_message_with_no_handler(self, mock_producer_class, minimal_kafka_config):
        """Test that messages without handlers are logged but don't error."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message for unregistered topic
        mock_message = Mock()
        mock_message.topic = "unregistered.topic"
        mock_message.key = "test-request-123"
        mock_message.value = {"request_id": "test-request-123"}

        # Should not raise exception
        await service._process_kafka_message(mock_message)

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_process_kafka_message_with_malformed_data(self, mock_producer_class, minimal_kafka_config):
        """Test that malformed messages are handled gracefully."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message with None value
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.key = "test-request-123"
        mock_message.value = None

        mock_handler = AsyncMock()
        service.register_handler("test.topic", mock_handler)

        # Should not raise exception or call handler
        await service._process_kafka_message(mock_message)
        mock_handler.assert_not_called()

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_process_kafka_message_handler_exception(self, mock_producer_class, minimal_kafka_config):
        """Test that handler exceptions are caught and logged."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.key = "test-request-123"
        mock_message.value = {"request_id": "test-request-123", "url": "https://example.com"}

        # Register a handler that raises exception
        mock_handler = AsyncMock(side_effect=Exception("Handler error"))
        service.register_handler("test.topic", mock_handler)

        # Should not raise exception (logged internally)
        await service._process_kafka_message(mock_message)


@pytest.mark.unit
class TestKafkaTransportServiceHandleOrchestratorRequest:
    """Test _handle_orchestrator_request method."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_handle_orchestrator_request_valid_event(self, mock_producer_class, minimal_kafka_config):
        """Test handling valid orchestrator request event."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService
        from models.orchestrator_models import StepInstruction
        from configs.models import WorkflowStepConfig

        mock_producer_instance = Mock()
        mock_producer_instance.send = Mock(return_value=Mock(get=Mock()))
        mock_producer_class.return_value = mock_producer_instance

        mock_orchestrator_service = Mock()

        # Mock orchestrator service to return StepInstruction
        mock_step_config = Mock(spec=WorkflowStepConfig)
        mock_step_config.name = "archive_generation"
        mock_step_config.component = "archive_generator"

        mock_instruction = Mock(spec=StepInstruction)
        mock_instruction.step_config = mock_step_config
        mock_instruction.request_id = "test-123"
        mock_instruction.component = "archive_generator"

        mock_orchestrator_service.start_workflow = Mock(return_value=mock_instruction)

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message
        mock_message = Mock()
        message_data = {
            "request_id": "test-123",
            "url": "https://example.com",
            "created_at": "2025-01-01T12:00:00Z"
        }

        # Call handler
        await service._handle_orchestrator_request(mock_message, message_data)

        # Verify orchestrator service was called
        mock_orchestrator_service.start_workflow.assert_called_once()

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_handle_orchestrator_request_invalid_event(self, mock_producer_class, minimal_kafka_config):
        """Test handling invalid orchestrator request (missing fields)."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = AsyncMock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Create mock message with missing required fields
        mock_message = Mock()
        message_data = {
            "request_id": "test-123"
            # Missing 'url' field
        }

        # Should handle validation error gracefully
        await service._handle_orchestrator_request(mock_message, message_data)

        # Orchestrator service should not be called
        mock_orchestrator_service.process_request.assert_not_called()


@pytest.mark.unit
class TestKafkaTransportServiceEventPublishing:
    """Test event publishing methods."""

    # REMOVED: _publish_event is no longer a method - EventPublisher handles this
    # Tests removed: test_publish_event_success, test_publish_event_failure, test_publish_event_no_producer
    # Event publishing is now tested via EventPublisher integration tests

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_send_response_calls_publish_event(self, mock_producer_class, minimal_kafka_config):
        """Test that send_response delegates to _publish_event."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_instance = Mock()
        mock_future = Mock()
        mock_future.get = Mock(return_value=None)
        mock_producer_instance.send = Mock(return_value=mock_future)
        mock_producer_class.return_value = mock_producer_instance

        mock_orchestrator_service = Mock()
        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Send response
        result = await service.send_response(
            destination="test.topic",
            message={"request_id": "test-123", "status": "completed"},
            key="test-123"
        )

        # Verify success
        assert result is True
        mock_producer_instance.send.assert_called_once()

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_send_response_without_key(self, mock_producer_class, minimal_kafka_config):
        """Test send_response without providing a key."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_instance = Mock()
        mock_future = Mock()
        mock_future.get = Mock(return_value=None)
        mock_producer_instance.send = Mock(return_value=mock_future)
        mock_producer_class.return_value = mock_producer_instance

        mock_orchestrator_service = Mock()
        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Send response without key
        result = await service.send_response(
            destination="test.topic",
            message={"request_id": "test-123"}
        )

        # Verify success
        assert result is True
        # Key should be None
        call_args = mock_producer_instance.send.call_args
        assert call_args[1]['key'] is None


@pytest.mark.unit
class TestKafkaTransportServiceStatusPublishing:
    """Test status event publishing methods."""

    # REMOVED: All status publishing methods are now internal and tested via transitions
    # Tests removed: test_publish_status_update, test_publish_orchestrator_completed,
    #                test_publish_orchestrator_failed, test_publish_orchestrator_request
    # Publishing is handled via _publish_workflow_completed and _publish_workflow_failed
    # and tested via integration tests with workflow transitions
    pass


@pytest.mark.unit
class TestKafkaTransportServiceLifecycle:
    """Test lifecycle management methods (stop)."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_stop_closes_consumer(self, mock_producer_class, minimal_kafka_config):
        """Test that stop() closes the Kafka consumer."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Mock consumer
        mock_consumer = Mock()
        service.consumer = mock_consumer
        service.running = True

        # Stop the service
        await service.stop()

        # Verify consumer was closed
        mock_consumer.close.assert_called_once()
        assert service.running is False

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_stop_closes_producer(self, mock_producer_class, minimal_kafka_config):
        """Test that stop() closes the Kafka producer."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_instance = Mock()
        mock_producer_class.return_value = mock_producer_instance
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)
        service.running = True

        # Stop the service
        await service.stop()

        # Verify producer was closed
        mock_producer_instance.close.assert_called_once()
        assert service.running is False

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_stop_handles_consumer_close_error(self, mock_producer_class, minimal_kafka_config):
        """Test that stop() handles consumer close errors gracefully."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Mock consumer that raises error on close
        mock_consumer = Mock()
        mock_consumer.close = Mock(side_effect=Exception("Close failed"))
        service.consumer = mock_consumer
        service.running = True

        # Should not raise exception
        await service.stop()

        # Service should still be stopped
        assert service.running is False

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_producer_class, minimal_kafka_config):
        """Test that stop() works even when service is not running."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_instance = Mock()
        mock_producer_class.return_value = mock_producer_instance
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)
        service.running = False

        # Should not raise exception
        await service.stop()

        assert service.running is False


@pytest.mark.unit
class TestKafkaTransportServiceHealthCheck:
    """Test health check functionality."""

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check_when_healthy(self, mock_producer_class, minimal_kafka_config):
        """Test health check returns healthy status when all components ready."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)
        service.running = True
        service.consumer = Mock()  # Simulate running consumer

        health = await service.health_check()

        assert health['healthy'] is True
        assert health['running'] is True
        assert health['details']['service'] == 'kafka_transport'
        assert health['details']['running'] is True
        assert health['details']['producer_ready'] is True
        assert health['details']['consumer_ready'] is True

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check_when_not_running(self, mock_producer_class, minimal_kafka_config):
        """Test health check when service is not running."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)
        service.running = False
        service.consumer = None

        health = await service.health_check()

        assert health['healthy'] is True  # Producer exists
        assert health['running'] is False
        assert health['details']['running'] is False
        assert health['details']['consumer_ready'] is False

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check_includes_kafka_config(self, mock_producer_class, minimal_kafka_config):
        """Test that health check includes Kafka configuration details."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        health = await service.health_check()

        # Health check returns basic status - kafka_config not in details
        assert 'details' in health
        assert health['details']['service'] == 'kafka_transport'
        # Kafka config is available via get_transport_info() instead

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check_includes_registered_topics(self, mock_producer_class, minimal_kafka_config):
        """Test that health check includes list of registered topics."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Register some handlers
        service.register_handler("topic1", lambda m, d: None)
        service.register_handler("topic2", lambda m, d: None)

        health = await service.health_check()

        assert 'registered_topics' in health['details']
        assert len(health['details']['registered_topics']) == 2
        assert "topic1" in health['details']['registered_topics']
        assert "topic2" in health['details']['registered_topics']

    @patch('transport_services.kafka.kafka_transport_service.KafkaProducer')
    @pytest.mark.asyncio
    async def test_health_check_error_handling(self, mock_producer_class, minimal_kafka_config):
        """Test that health check handles errors gracefully."""
        from transport_services.kafka.kafka_transport_service import KafkaTransportService

        mock_producer_class.return_value = Mock()
        mock_orchestrator_service = Mock()

        service = KafkaTransportService(minimal_kafka_config, mock_orchestrator_service)

        # Mock a property that raises an error
        type(service).running = property(lambda self: (_ for _ in ()).throw(Exception("Test error")))

        health = await service.health_check()

        # Should return unhealthy status with error
        assert health['healthy'] is False
        assert 'error' in health
