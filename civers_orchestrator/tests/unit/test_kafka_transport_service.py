# tests/unit/test_kafka_transport_service.py
"""Unit tests for Kafka Transport Service.

Tests are written against the actual aiokafka-based architecture:
- KafkaTransportService.__init__ creates a KafkaConnectionManager but makes NO
  network calls. Producer/consumer are None until start() is called.
- Connections live on service.connection_manager.producer / .consumer
- Async lifecycle methods (start/stop) are tested by mocking connection_manager
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from configs.models import (
    ConfigDataModel, AppConfig, TransportConfig, KafkaConfig,
    KafkaConsumerConfig, KafkaProducerConfig, KafkaTopicsConfig,
    KafkaComponentMapping,
)
from transport_services.transport_service_interface import TransportServiceInterface


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_kafka_config():
    """Minimal ConfigDataModel with two component mappings."""
    return ConfigDataModel(
        app=AppConfig(name="test-orchestrator", version="1.0.0", environment="testing"),
        transport=TransportConfig(
            enabled=["kafka"],
            kafka=KafkaConfig(
                bootstrap_servers="localhost:29092",
                consumer=KafkaConsumerConfig(
                    group_id="test-orchestrator-group",
                    auto_offset_reset="earliest",
                ),
                producer=KafkaProducerConfig(acks="all", retries=3),
                topics=KafkaTopicsConfig(
                    orchestrator_requests="test.orchestrator.requests",
                    orchestrator_status="test.orchestrator.status",
                    orchestrator_completed="test.orchestrator.completed",
                    orchestrator_failed="test.orchestrator.failed",
                ),
                component_mappings={
                    "archive_generator": KafkaComponentMapping(
                        step_name="archive_generation",
                        request_topic="archive.requests",
                        response_topics={"success": "archive.completed", "failure": "archive.failed"},
                        event_models={
                            "request": "ArchiveRequestEvent",
                            "success": "ArchiveCompletedEvent",
                            "failure": "ArchiveFailedEvent",
                        },
                    ),
                    "metadata_extractor": KafkaComponentMapping(
                        step_name="metadata_extraction",
                        request_topic="metadata.requests",
                        response_topics={"success": "metadata.completed", "failure": "metadata.failed"},
                        event_models={
                            "request": "MetadataExtractionRequestEvent",
                            "success": "MetadataExtractionCompletedEvent",
                            "failure": "MetadataExtractionFailedEvent",
                        },
                    ),
                },
            ),
        ),
        domains=[],
        workflows=[],
    )


@pytest.fixture
def service(minimal_kafka_config):
    """Instantiated KafkaTransportService with a mock orchestrator."""
    from transport_services.kafka.kafka_transport_service import KafkaTransportService
    return KafkaTransportService(minimal_kafka_config, Mock())


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceInitialization:

    def test_init_stores_config(self, service, minimal_kafka_config):
        assert service.config == minimal_kafka_config
        assert service.kafka_config == minimal_kafka_config.transport.kafka
        assert service.topics == minimal_kafka_config.transport.kafka.topics

    def test_init_not_running(self, service):
        assert service.running is False

    def test_init_no_connections(self, service):
        """No Kafka connections are made during __init__."""
        assert service.connection_manager.producer is None
        assert service.connection_manager.consumer is None

    def test_init_empty_event_handlers(self, service):
        assert isinstance(service.event_handlers, dict)
        assert len(service.event_handlers) == 0

    def test_init_adapter_created(self, service):
        assert service.adapter is not None

    def test_init_topic_to_step_name_map(self, service):
        """Reverse map from response topics to step names is built at init."""
        m = service._topic_to_step_name
        assert m["archive.completed"] == "archive_generation"
        assert m["archive.failed"] == "archive_generation"
        assert m["metadata.completed"] == "metadata_extraction"
        assert m["metadata.failed"] == "metadata_extraction"


# ---------------------------------------------------------------------------
# Interface compliance
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceInterface:

    def test_is_transport_service_interface(self, service):
        assert isinstance(service, TransportServiceInterface)

    def test_has_required_methods(self, service):
        for method in ("start", "stop", "register_handler", "health_check",
                       "send_response", "get_transport_info"):
            assert hasattr(service, method)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceConfiguration:

    def test_kafka_config_extraction(self, service):
        assert service.kafka_config.bootstrap_servers == "localhost:29092"
        assert service.kafka_config.consumer.group_id == "test-orchestrator-group"
        assert service.kafka_config.producer.acks == "all"
        assert service.kafka_config.producer.retries == 3

    def test_topics_configuration(self, service):
        assert service.topics.orchestrator_requests == "test.orchestrator.requests"
        assert service.topics.orchestrator_status == "test.orchestrator.status"
        assert service.topics.orchestrator_completed == "test.orchestrator.completed"
        assert service.topics.orchestrator_failed == "test.orchestrator.failed"


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceEventHandling:

    def test_register_handler(self, service):
        def handler(msg, data): pass
        service.register_handler("test.topic", handler)
        assert "test.topic" in service.event_handlers
        assert service.event_handlers["test.topic"] == handler

    def test_register_multiple_handlers(self, service):
        def h1(m, d): pass
        def h2(m, d): pass
        service.register_handler("topic1", h1)
        service.register_handler("topic2", h2)
        assert len(service.event_handlers) == 2


# ---------------------------------------------------------------------------
# get_transport_info
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceGetTransportInfo:

    def test_structure(self, service):
        info = service.get_transport_info()
        assert info["transport_type"] == "KafkaTransportService"
        assert "kafka_config" in info
        assert "status" in info

    def test_kafka_config_fields(self, service):
        cfg = service.get_transport_info()["kafka_config"]
        assert cfg["bootstrap_servers"] == "localhost:29092"
        assert cfg["consumer_group"] == "test-orchestrator-group"

    def test_status_before_start(self, service):
        status = service.get_transport_info()["status"]
        assert status["running"] is False
        assert status["producer_ready"] is False   # not started yet
        assert status["consumer_ready"] is False


# ---------------------------------------------------------------------------
# Safe JSON deserializer (lives on KafkaConnectionManager)
# ---------------------------------------------------------------------------

class TestSafeJsonDeserializer:

    def test_valid_json(self):
        from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager
        result = KafkaConnectionManager._safe_json_deserializer(
            b'{"request_id": "123", "url": "https://example.com"}'
        )
        assert isinstance(result, dict)
        assert result["request_id"] == "123"

    def test_none_returns_none(self):
        from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager
        assert KafkaConnectionManager._safe_json_deserializer(None) is None

    def test_invalid_json_returns_raw(self):
        from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager
        result = KafkaConnectionManager._safe_json_deserializer(b"not json at all")
        # Falls back to raw bytes (not None, not a dict)
        assert result is not None
        assert not isinstance(result, dict)


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceStart:

    @pytest.mark.asyncio
    async def test_start_registers_default_handlers(self, service):
        service.connection_manager.setup_producer = AsyncMock()
        service.connection_manager.setup_consumer = AsyncMock()
        service._consume_loop = AsyncMock()

        await service.start()

        assert "test.orchestrator.requests" in service.event_handlers
        assert service.running is True

    @pytest.mark.asyncio
    async def test_start_calls_setup_producer_and_consumer(self, service):
        service.connection_manager.setup_producer = AsyncMock()
        service.connection_manager.setup_consumer = AsyncMock()
        service._consume_loop = AsyncMock()

        await service.start()

        service.connection_manager.setup_producer.assert_called_once()
        service.connection_manager.setup_consumer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure_calls_stop(self, service):
        service.connection_manager.setup_producer = AsyncMock(
            side_effect=Exception("Producer setup failed")
        )
        service.stop = AsyncMock()

        with pytest.raises(Exception, match="Producer setup failed"):
            await service.start()

        service.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Message processing
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceMessageProcessing:

    @pytest.mark.asyncio
    async def test_routes_to_registered_handler(self, service):
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.value = {"request_id": "req-1", "url": "https://example.com"}

        mock_handler = AsyncMock()
        service.register_handler("test.topic", mock_handler)

        await service._process_message(mock_message)

        mock_handler.assert_called_once_with(mock_message, mock_message.value)

    @pytest.mark.asyncio
    async def test_no_handler_does_not_raise(self, service):
        mock_message = Mock()
        mock_message.topic = "unregistered.topic"
        mock_message.value = {"request_id": "req-1"}
        await service._process_message(mock_message)  # must not raise

    @pytest.mark.asyncio
    async def test_none_value_skips_handler(self, service):
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.value = None

        mock_handler = AsyncMock()
        service.register_handler("test.topic", mock_handler)

        await service._process_message(mock_message)
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_exception_is_caught(self, service):
        mock_message = Mock()
        mock_message.topic = "test.topic"
        mock_message.value = {"request_id": "req-1", "url": "https://example.com"}

        service.register_handler("test.topic", AsyncMock(side_effect=Exception("boom")))
        await service._process_message(mock_message)  # must not raise


# ---------------------------------------------------------------------------
# _handle_orchestrator_request
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceHandleOrchestratorRequest:

    @pytest.mark.asyncio
    async def test_valid_request_calls_start_workflow(self, service):
        from models.orchestrator_models import StepInstruction
        from configs.models import WorkflowStepConfig

        mock_step = Mock(spec=WorkflowStepConfig)
        mock_step.name = "archive_generation"
        mock_step.component = "archive_generator"

        mock_instruction = Mock(spec=StepInstruction)
        mock_instruction.step_config = mock_step
        mock_instruction.request_id = "test-123"
        mock_instruction.component = "archive_generator"

        service.orchestrator.start_workflow = Mock(return_value=mock_instruction)
        service._execute_step_instruction = AsyncMock()

        await service._handle_orchestrator_request(
            Mock(),
            {"request_id": "test-123", "url": "https://example.com", "created_at": "2025-01-01T12:00:00Z"},
        )

        service.orchestrator.start_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_url_does_not_call_start_workflow(self, service):
        service.orchestrator.start_workflow = Mock()

        await service._handle_orchestrator_request(
            Mock(),
            {"request_id": "test-123"},  # missing url
        )

        service.orchestrator.start_workflow.assert_not_called()


# ---------------------------------------------------------------------------
# send_response
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceEventPublishing:

    @pytest.mark.asyncio
    async def test_send_response_with_producer_returns_true(self, service):
        mock_producer = AsyncMock()
        mock_producer.send = AsyncMock()
        service.connection_manager.producer = mock_producer

        result = await service.send_response(
            destination="test.topic",
            message={"request_id": "test-123"},
            key="test-123",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_response_without_producer_returns_false(self, service):
        service.connection_manager.producer = None

        result = await service.send_response(
            destination="test.topic",
            message={"request_id": "test-123"},
        )

        assert result is False


# ---------------------------------------------------------------------------
# stop() / lifecycle
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceLifecycle:

    @pytest.mark.asyncio
    async def test_stop_calls_cleanup(self, service):
        service.connection_manager.cleanup = AsyncMock()
        service.running = True

        await service.stop()

        service.connection_manager.cleanup.assert_called_once()
        assert service.running is False

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, service):
        service.connection_manager.cleanup = AsyncMock()
        service.running = True
        await service.stop()
        assert service.running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, service):
        service.connection_manager.cleanup = AsyncMock()
        service.running = False
        await service.stop()  # must not raise
        assert service.running is False


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------

class TestKafkaTransportServiceHealthCheck:

    @pytest.mark.asyncio
    async def test_healthy_when_running_with_producer(self, service):
        service.running = True
        service.connection_manager.producer = Mock()
        service.connection_manager.consumer = Mock()

        health = await service.health_check()

        assert health["healthy"] is True
        assert health["running"] is True
        assert health["details"]["service"] == "kafka_transport"
        assert health["details"]["producer_ready"] is True
        assert health["details"]["consumer_ready"] is True

    @pytest.mark.asyncio
    async def test_not_healthy_when_not_running(self, service):
        service.running = False
        service.connection_manager.producer = None
        service.connection_manager.consumer = None

        health = await service.health_check()

        assert health["healthy"] is False
        assert health["running"] is False
        assert health["details"]["producer_ready"] is False
        assert health["details"]["consumer_ready"] is False

    @pytest.mark.asyncio
    async def test_includes_registered_topics(self, service):
        service.connection_manager.producer = None
        service.connection_manager.consumer = None
        service.register_handler("topic1", lambda m, d: None)
        service.register_handler("topic2", lambda m, d: None)

        health = await service.health_check()

        assert "registered_topics" in health["details"]
        assert set(health["details"]["registered_topics"]) == {"topic1", "topic2"}

    @pytest.mark.asyncio
    async def test_error_returns_unhealthy(self, service):
        # Force an exception inside health_check
        type(service).running = property(
            lambda self: (_ for _ in ()).throw(Exception("internal error"))
        )
        health = await service.health_check()
        assert health["healthy"] is False
        assert "error" in health
