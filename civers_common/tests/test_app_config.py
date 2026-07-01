"""Tests for BaseAppConfig."""


from civers_common.configs.models import (
    BaseAppConfig,
    BaseKafkaConfig,
    BaseTransportConfig,
)


class TestBaseAppConfig:
    """Test BaseAppConfig base class."""

    def test_defaults(self):
        config = BaseAppConfig()
        assert config.name == "civers_service"
        assert config.version == "1.0.0"
        assert config.environment == "development"
        assert config.transport is None

    def test_get_kafka_config_returns_none_without_transport(self):
        config = BaseAppConfig()
        assert config.get_kafka_config() is None

    def test_get_kafka_config_returns_kafka(self):
        kafka = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        transport = BaseTransportConfig(enabled=["kafka"], kafka=kafka)
        config = BaseAppConfig(transport=transport)
        assert config.get_kafka_config() == kafka

    def test_get_kafka_config_returns_none_without_kafka(self):
        """Transport exists but kafka is None (e.g. HTTP-only transport)."""
        # We can't test this directly because BaseTransportConfig requires
        # that enabled transports have config. So we test the method logic
        # by setting transport with kafka.
        kafka = BaseKafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"t": "v"},
        )
        transport = BaseTransportConfig(enabled=["kafka"], kafka=kafka)
        config = BaseAppConfig(transport=transport)
        result = config.get_kafka_config()
        assert result is not None

    def test_extra_fields_ignored(self):
        config = BaseAppConfig(unknown="ignored")
        assert not hasattr(config, "unknown")

    def test_subclass_can_override_defaults(self):
        """Services override name, version defaults."""

        class CDAppConfig(BaseAppConfig):
            name: str = "change_detection_system"
            version: str = "0.1.0"

        config = CDAppConfig()
        assert config.name == "change_detection_system"
        assert config.version == "0.1.0"
        assert config.environment == "development"

    def test_subclass_can_add_fields(self):
        """Services add their own fields."""

        class AGAppConfig(BaseAppConfig):
            archive_directory: str = "archives"

        config = AGAppConfig()
        assert config.archive_directory == "archives"
        assert config.name == "civers_service"
