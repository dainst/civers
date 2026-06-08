"""Tests for BaseKafkaConfig."""

import pytest
from pydantic import ValidationError

from civers_common.configs.models import BaseKafkaConfig


class TestBaseKafkaConfig:
    """Test BaseKafkaConfig base class."""

    def test_valid_config(self):
        config = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"requests": "test.requests"},
        )
        assert config.bootstrap_servers == "localhost:9092"
        assert config.topics == {"requests": "test.requests"}

    def test_default_consumer_group(self):
        config = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        assert config.consumer_group == "civers_default_group"

    def test_empty_bootstrap_servers_rejected(self):
        with pytest.raises(ValidationError):
            BaseKafkaConfig(bootstrap_servers="  ", topics={"t": "v"})

    def test_blank_bootstrap_servers_rejected(self):
        with pytest.raises(ValidationError):
            BaseKafkaConfig(bootstrap_servers="", topics={"t": "v"})

    def test_bootstrap_servers_stripped(self):
        config = BaseKafkaConfig(
            bootstrap_servers="  localhost:9092  ",
            topics={"t": "v"},
        )
        assert config.bootstrap_servers == "localhost:9092"

    def test_empty_topics_rejected(self):
        with pytest.raises(ValidationError):
            BaseKafkaConfig(bootstrap_servers="localhost:9092", topics={})

    def test_sync_consumer_group_from_nested(self):
        config = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
            consumer={"group_id": "my_group"},
        )
        assert config.consumer_group == "my_group"

    def test_consumer_none_by_default(self):
        config = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        assert config.consumer is None

    def test_extra_fields_ignored(self):
        config = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
            unknown="ignored",
        )
        assert not hasattr(config, "unknown")

    def test_subclass_inherits_validators(self):
        """Verify a subclass gets all base validators for free."""

        class MyKafkaConfig(BaseKafkaConfig):
            extra_field: str = "hello"

        with pytest.raises(ValidationError):
            MyKafkaConfig(bootstrap_servers="", topics={"t": "v"})

        config = MyKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
            consumer={"group_id": "sub_group"},
        )
        assert config.consumer_group == "sub_group"
        assert config.extra_field == "hello"

    def test_subclass_can_override_default_consumer_group(self):
        """Service-specific default consumer_group."""

        class CDKafkaConfig(BaseKafkaConfig):
            consumer_group: str = "change_detection_group"

        config = CDKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        assert config.consumer_group == "change_detection_group"
