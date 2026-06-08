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
