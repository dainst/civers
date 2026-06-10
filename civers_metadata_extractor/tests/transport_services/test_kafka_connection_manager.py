"""
Unit tests for KafkaConnectionManager

Tests cover all functionality including connection setup, health checks,
configuration validation, error handling, and resource cleanup.

Uses real configuration from tests/test_app_config.yaml to ensure tests
match actual production configuration structure.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiokafka.errors import KafkaError

from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager


@pytest.fixture
def mock_kafka_config():
    """Load Kafka configuration from test_app_config.yaml."""
    import os

    import yaml

    from configs.models import ConfigDataModel

    # Get path to test config file
    test_config_path = os.path.join(os.path.dirname(__file__), "..", "test_app_config.yaml")
    with open(test_config_path) as f:
        data = yaml.safe_load(f)
    config = ConfigDataModel(**data)

    return config.app.transport.kafka


@pytest.fixture
def connection_manager(mock_kafka_config):
    """Create KafkaConnectionManager instance for testing."""
    return KafkaConnectionManager(mock_kafka_config)


class TestKafkaConnectionManagerInitialization:
    """Test KafkaConnectionManager initialization and basic properties."""

    def test_initialization_with_valid_config(self, connection_manager, mock_kafka_config):
        """Test proper initialization with valid configuration."""
        assert connection_manager.kafka_config == mock_kafka_config
        assert connection_manager.producer is None
        assert connection_manager.consumer is None
        assert connection_manager._connection_status["producer_started"] is False
        assert connection_manager._connection_status["consumer_started"] is False

    def test_connection_status_initial_state(self, connection_manager):
        """Test initial connection status state."""
        status = connection_manager.get_connection_status()

        assert status["producer_started"] is False
        assert status["consumer_started"] is False
        # Ensure we get a copy, not the original dict
        status["producer_started"] = True
        assert connection_manager._connection_status["producer_started"] is False


class TestProducerSetup:
    """Test Kafka producer setup functionality."""

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaProducer")
    async def test_setup_producer_success(self, mock_producer_class, connection_manager):
        """Test successful producer setup."""
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        result = await connection_manager.setup_producer()

        # Verify producer was created with correct configuration
        _, call_kwargs = mock_producer_class.call_args
        assert call_kwargs["bootstrap_servers"] == "localhost:29092"  # From test_app_config.yaml
        assert call_kwargs["acks"] == 1
        assert call_kwargs["retry_backoff_ms"] == 1000
        assert call_kwargs["request_timeout_ms"] == 30000
        assert call_kwargs["max_request_size"] == 1048576
        # Verify serializers are callable functions
        assert callable(call_kwargs["value_serializer"])
        assert callable(call_kwargs["key_serializer"])

        # Verify internal state updated
        assert connection_manager.producer == mock_producer
        assert connection_manager._connection_status["producer_started"] is True
        assert result == mock_producer

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaProducer")
    async def test_setup_producer_failure(self, mock_producer_class, connection_manager):
        """Test producer setup failure handling."""
        mock_producer_class.side_effect = Exception("Connection failed")

        with pytest.raises(KafkaError, match="Producer setup failed"):
            await connection_manager.setup_producer()

        # Verify internal state reflects failure
        assert connection_manager.producer is None
        assert connection_manager._connection_status["producer_started"] is False

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaProducer")
    async def test_producer_serializers(self, mock_producer_class, connection_manager):
        """Test that producer serializers work correctly."""
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        await connection_manager.setup_producer()

        # Get the actual serializers used
        call_args = mock_producer_class.call_args
        value_serializer = call_args[1]["value_serializer"]
        key_serializer = call_args[1]["key_serializer"]

        # Test value serializer
        test_data = {"test": "data", "number": 123}
        serialized_value = value_serializer(test_data)
        expected_value = json.dumps(test_data, default=str).encode("utf-8")
        assert serialized_value == expected_value

        # Test key serializer
        test_key = "test_key"
        serialized_key = key_serializer(test_key)
        assert serialized_key == test_key.encode("utf-8")

        # Test key serializer with None
        assert key_serializer(None) is None


class TestConsumerSetup:
    """Test Kafka consumer setup functionality."""

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaConsumer")
    async def test_setup_consumer_success(self, mock_consumer_class, connection_manager):
        """Test successful consumer setup."""
        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer_class.return_value = mock_consumer

        topics = ["test.topic1", "test.topic2"]
        result = await connection_manager.setup_consumer(topics)

        # Verify consumer was created with correct configuration
        call_args, call_kwargs = mock_consumer_class.call_args
        assert call_args == tuple(topics)
        assert call_kwargs["bootstrap_servers"] == "localhost:29092"  # From test_app_config.yaml
        assert call_kwargs["group_id"] == "metadata_extraction_group"  # From test_app_config.yaml
        assert call_kwargs["auto_offset_reset"] == "earliest"
        assert call_kwargs["enable_auto_commit"] is True
        assert call_kwargs["request_timeout_ms"] == 30000
        # Verify deserializers are callable functions
        assert callable(call_kwargs["value_deserializer"])
        assert callable(call_kwargs["key_deserializer"])

        # Verify internal state updated
        assert connection_manager.consumer == mock_consumer
        assert connection_manager._connection_status["consumer_started"] is True
        assert result == mock_consumer

    async def test_setup_consumer_empty_topics(self, connection_manager):
        """Test consumer setup with empty topics list."""
        with pytest.raises(ValueError, match="At least one topic must be provided"):
            await connection_manager.setup_consumer([])

    async def test_setup_consumer_none_topics(self, connection_manager):
        """Test consumer setup with None topics."""
        with pytest.raises(ValueError, match="At least one topic must be provided"):
            await connection_manager.setup_consumer(None)

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaConsumer")
    async def test_setup_consumer_failure(self, mock_consumer_class, connection_manager):
        """Test consumer setup failure handling."""
        mock_consumer_class.side_effect = Exception("Consumer creation failed")

        with pytest.raises(KafkaError, match="Consumer setup failed"):
            await connection_manager.setup_consumer(["test.topic"])

        # Verify internal state reflects failure
        assert connection_manager.consumer is None
        assert connection_manager._connection_status["consumer_started"] is False

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaConsumer")
    async def test_consumer_deserializers(self, mock_consumer_class, connection_manager):
        """Test that consumer deserializers work correctly."""
        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer_class.return_value = mock_consumer

        await connection_manager.setup_consumer(["test.topic"])

        # Get the actual deserializers used
        call_args = mock_consumer_class.call_args
        value_deserializer = call_args[1]["value_deserializer"]
        key_deserializer = call_args[1]["key_deserializer"]

        # Test value deserializer
        test_data = {"test": "data", "number": 123}
        mock_message = Mock()
        mock_message.decode.return_value = json.dumps(test_data)

        deserialized_value = value_deserializer(mock_message)
        assert deserialized_value == test_data

        # Test key deserializer
        test_key = "test_key"
        mock_key = Mock()
        mock_key.decode.return_value = test_key

        deserialized_key = key_deserializer(mock_key)
        assert deserialized_key == test_key

        # Test key deserializer with None
        assert key_deserializer(None) is None


class TestConfigurationValidation:
    """Test configuration validation functionality."""

    def test_validate_configuration_success(self, connection_manager):
        """Test successful configuration validation."""
        result = connection_manager.validate_configuration()

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0
        assert result["topics_count"] == 8  # All topics from test_app_config.yaml

    def test_validate_configuration_missing_bootstrap_servers(self, mock_kafka_config):
        """Test validation with missing bootstrap servers."""
        mock_kafka_config.bootstrap_servers = ""
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is False
        assert "Bootstrap servers not configured" in result["errors"]

    def test_validate_configuration_invalid_bootstrap_servers(self, mock_kafka_config):
        """Test validation with invalid bootstrap servers type."""
        mock_kafka_config.bootstrap_servers = 12345  # Invalid type
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is False
        assert "Bootstrap servers must be a string" in result["errors"]

    def test_validate_configuration_missing_consumer_group(self, mock_kafka_config):
        """Test validation with missing consumer group."""
        mock_kafka_config.consumer_group = ""
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is False
        assert "Consumer group not configured" in result["errors"]

    def test_validate_configuration_no_topics(self, mock_kafka_config):
        """Test validation with no topics configured."""
        mock_kafka_config.topics = {}
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is False  # No topics is an error
        assert "At least one topic must be configured" in result["errors"]
        assert result["topics_count"] == 0

    def test_validate_configuration_invalid_topics_type(self, mock_kafka_config):
        """Test validation with invalid topics type."""
        mock_kafka_config.topics = "invalid"  # Should be dict
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is False
        assert "Topics must be a dictionary" in result["errors"]

    def test_validate_configuration_with_some_topics(self, mock_kafka_config):
        """Test validation with some topics configured."""
        # Set some topics
        mock_kafka_config.topics = {
            "metadata_extraction_requests": "test.requests",
            "metadata_extraction_completed": "test.completed",
            "metadata_quality": "test.quality",
        }
        connection_manager = KafkaConnectionManager(mock_kafka_config)

        result = connection_manager.validate_configuration()

        assert result["valid"] is True  # Some topics should be valid
        assert result["topics_count"] == 3


class TestCleanup:
    """Test connection cleanup functionality."""

    async def test_cleanup_with_no_connections(self, connection_manager):
        """Test cleanup when no connections exist."""
        await connection_manager.cleanup()

        # Should complete without errors
        assert connection_manager.producer is None
        assert connection_manager.consumer is None
        status = connection_manager.get_connection_status()
        assert status["producer_started"] is False
        assert status["consumer_started"] is False

    async def test_cleanup_with_producer(self, connection_manager):
        """Test cleanup with active producer."""
        mock_producer = AsyncMock()
        mock_producer.stop = AsyncMock()  # aiokafka uses stop() instead of close()
        connection_manager.producer = mock_producer
        connection_manager._connection_status["producer_started"] = True

        await connection_manager.cleanup()

        mock_producer.stop.assert_called_once()
        assert connection_manager.producer is None
        status = connection_manager.get_connection_status()
        assert status["producer_started"] is False

    async def test_cleanup_with_consumer(self, connection_manager):
        """Test cleanup with active consumer."""
        mock_consumer = AsyncMock()
        mock_consumer.stop = AsyncMock()  # aiokafka uses stop() instead of close()
        connection_manager.consumer = mock_consumer
        connection_manager._connection_status["consumer_started"] = True

        await connection_manager.cleanup()

        mock_consumer.stop.assert_called_once()
        assert connection_manager.consumer is None
        status = connection_manager.get_connection_status()
        assert status["consumer_started"] is False

    async def test_cleanup_with_producer_error(self, connection_manager):
        """Test cleanup handles producer stop errors gracefully."""
        mock_producer = AsyncMock()
        mock_producer.stop.side_effect = Exception("Stop failed")
        connection_manager.producer = mock_producer

        # Should not raise exception
        await connection_manager.cleanup()

        # Producer should still be set to None despite error
        assert connection_manager.producer is None

    async def test_cleanup_with_consumer_error(self, connection_manager):
        """Test cleanup handles consumer stop errors gracefully."""
        mock_consumer = AsyncMock()
        mock_consumer.stop.side_effect = Exception("Consumer stop failed")
        connection_manager.consumer = mock_consumer

        # Should not raise exception
        await connection_manager.cleanup()

        # Consumer should still be set to None despite error
        assert connection_manager.consumer is None

    async def test_cleanup_resets_status(self, connection_manager):
        """Test that cleanup properly resets connection status."""
        # Setup active connections
        connection_manager.producer = Mock()
        connection_manager.consumer = Mock()
        connection_manager._connection_status = {
            "producer_started": True,
            "consumer_started": True,
        }

        await connection_manager.cleanup()

        # Verify status is reset
        status = connection_manager.get_connection_status()
        assert status["producer_started"] is False
        assert status["consumer_started"] is False


class TestErrorHandling:
    """Test error handling in various scenarios."""

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaProducer")
    async def test_producer_setup_kafka_error(self, mock_producer_class, connection_manager):
        """Test handling of KafkaError during producer setup."""
        mock_producer_class.side_effect = KafkaError("Kafka connection failed")

        with pytest.raises(KafkaError, match="Producer setup failed"):
            await connection_manager.setup_producer()

        assert connection_manager._connection_status["producer_started"] is False

    @patch("transport_services.kafka.kafka_connection_manager.AIOKafkaConsumer")
    async def test_consumer_setup_kafka_error(self, mock_consumer_class, connection_manager):
        """Test handling of KafkaError during consumer setup."""
        mock_consumer_class.side_effect = KafkaError("Kafka consumer failed")

        with pytest.raises(KafkaError, match="Consumer setup failed"):
            await connection_manager.setup_consumer(["test.topic"])

        assert connection_manager._connection_status["consumer_started"] is False
