"""Tests for BaseTransportConfig."""

import pytest
from pydantic import ValidationError

from civers_common.configs.models import BaseKafkaConfig, BaseTransportConfig


class TestBaseTransportConfig:
    """Test BaseTransportConfig base class."""

    def test_valid_config(self):
        kafka = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        config = BaseTransportConfig(enabled=["kafka"], kafka=kafka)
        assert config.enabled == ["kafka"]
        assert config.kafka is not None

    def test_empty_enabled_rejected(self):
        with pytest.raises(ValidationError, match="At least one transport"):
            BaseTransportConfig(enabled=[])

    def test_enabled_transport_without_config_rejected(self):
        with pytest.raises(ValidationError, match="enabled but not configured"):
            BaseTransportConfig(enabled=["kafka"])

    def test_unsupported_transport_rejected(self):
        with pytest.raises(ValidationError, match="not supported"):
            BaseTransportConfig(enabled=["redis"])

    def test_kafka_none_by_default(self):
        """kafka field defaults to None — requires enabled list."""
        kafka = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        config = BaseTransportConfig(enabled=["kafka"], kafka=kafka)
        assert config.kafka == kafka

    def test_extra_fields_ignored(self):
        kafka = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        config = BaseTransportConfig(
            enabled=["kafka"],
            kafka=kafka,
            unknown="ignored",
        )
        assert not hasattr(config, "unknown")

    def test_subclass_can_override_kafka_type(self):
        """Services override kafka field type with their own KafkaConfig subclass."""

        class MyKafkaConfig(BaseKafkaConfig):
            extra: str = "value"

        class MyTransportConfig(BaseTransportConfig):
            kafka: MyKafkaConfig | None = None

        kafka = MyKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        config = MyTransportConfig(enabled=["kafka"], kafka=kafka)
        assert config.kafka.extra == "value"


class TestBaseTransportConfigExtensible:
    """Tests for the generic transports extensibility on BaseTransportConfig."""

    def _kafka(self) -> BaseKafkaConfig:
        return BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )

    def test_is_transport_enabled_true(self):
        config = BaseTransportConfig(enabled=["kafka"], kafka=self._kafka())
        assert config.is_transport_enabled("kafka") is True

    def test_is_transport_enabled_false(self):
        config = BaseTransportConfig(enabled=["kafka"], kafka=self._kafka())
        assert config.is_transport_enabled("http") is False

    def test_get_transport_config_kafka(self):
        kafka = self._kafka()
        config = BaseTransportConfig(enabled=["kafka"], kafka=kafka)
        result = config.get_transport_config("kafka")
        assert result is not None
        assert result["bootstrap_servers"] == "localhost:9092"

    def test_get_transport_config_generic(self):
        config = BaseTransportConfig(
            enabled=["kafka", "http"],
            kafka=self._kafka(),
            transports={"http": {"host": "localhost", "port": 8080}},
        )
        result = config.get_transport_config("http")
        assert result == {"host": "localhost", "port": 8080}

    def test_get_transport_config_unknown_returns_none(self):
        config = BaseTransportConfig(enabled=["kafka"], kafka=self._kafka())
        assert config.get_transport_config("grpc") is None

    def test_generic_transport_in_transports_dict_is_valid(self):
        """A transport enabled via the transports dict must not raise."""
        config = BaseTransportConfig(
            enabled=["kafka", "http"],
            kafka=self._kafka(),
            transports={"http": {"host": "localhost"}},
        )
        assert config.is_transport_enabled("http") is True

    def test_enabled_transport_not_in_kafka_nor_transports_raises(self):
        """Enabling a transport with no config in kafka or transports dict raises."""
        with pytest.raises(ValidationError, match="not supported"):
            BaseTransportConfig(
                enabled=["kafka", "grpc"],
                kafka=self._kafka(),
            )

    def test_transports_defaults_to_empty(self):
        config = BaseTransportConfig(enabled=["kafka"], kafka=self._kafka())
        assert config.transports == {}
