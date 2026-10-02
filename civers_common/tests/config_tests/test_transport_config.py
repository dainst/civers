"""Tests for BaseTransportConfig."""

import pytest
from pydantic import BaseModel, Field, ValidationError

from civers_common.configs.models import BaseTransportConfig

_KAFKA = {"bootstrap_servers": "localhost:9092", "topics": {"t": "v"}}


def _config(**kwargs) -> BaseTransportConfig:
    defaults = {"enabled": ["kafka"], "transports": {"kafka": _KAFKA}}
    return BaseTransportConfig(**{**defaults, **kwargs})


class TestBaseTransportConfig:
    """Test BaseTransportConfig base class."""

    def test_valid_config(self):
        config = _config()
        assert config.enabled == ["kafka"]
        assert config.transports["kafka"] == _KAFKA

    def test_empty_enabled_rejected(self):
        with pytest.raises(ValidationError, match="At least one transport"):
            BaseTransportConfig(enabled=[])

    def test_enabled_transport_without_config_rejected(self):
        with pytest.raises(ValidationError, match="enabled but not configured"):
            BaseTransportConfig(enabled=["kafka"])

    def test_enabled_transport_without_transports_entry_rejected(self):
        with pytest.raises(ValidationError, match="not configured under 'transports'"):
            BaseTransportConfig(enabled=["redis"])

    def test_no_transport_is_privileged_on_the_base(self):
        """Every transport is a peer under ``transports``; the base declares no typed field."""
        assert "kafka" not in BaseTransportConfig.model_fields

    def test_extra_fields_ignored(self):
        config = _config(unknown="ignored")
        assert not hasattr(config, "unknown")

    def test_subclass_typed_field_counts_as_configured(self):
        """A subclass may declare a typed field named after a transport (AWI pattern)."""

        class RestConfig(BaseModel):
            port: int = 8100

        class MyTransportConfig(BaseTransportConfig):
            enabled: list[str] = Field(default_factory=lambda: ["rest"])
            rest: RestConfig = Field(default_factory=RestConfig)

        config = MyTransportConfig()
        assert config.transports == {}
        assert config.is_transport_enabled("rest") is True
        assert config.get_transport_config("rest") == {"port": 8100}


class TestBaseTransportConfigExtensible:
    """Tests for the generic transports extensibility on BaseTransportConfig."""

    def test_is_transport_enabled_true(self):
        assert _config().is_transport_enabled("kafka") is True

    def test_is_transport_enabled_false(self):
        assert _config().is_transport_enabled("http") is False

    def test_get_transport_config_returns_raw_entry(self):
        assert _config().get_transport_config("kafka") == _KAFKA

    def test_get_transport_config_generic(self):
        config = _config(
            enabled=["kafka", "http"],
            transports={"kafka": _KAFKA, "http": {"host": "localhost", "port": 8080}},
        )
        assert config.get_transport_config("http") == {"host": "localhost", "port": 8080}

    def test_get_transport_config_unknown_returns_none(self):
        assert _config().get_transport_config("grpc") is None

    def test_enabled_transport_missing_from_transports_raises(self):
        with pytest.raises(ValidationError, match="not configured under 'transports'"):
            _config(enabled=["kafka", "grpc"])


class TestKafkaConfiguration:
    """The base model requires Kafka configuration under ``transports``."""

    def test_top_level_kafka_does_not_configure_the_base_model(self):
        with pytest.raises(ValidationError, match="'kafka' is enabled but not configured"):
            BaseTransportConfig(enabled=["kafka"], kafka=_KAFKA)

    def test_top_level_kafka_does_not_override_explicit_configuration(self):
        config = BaseTransportConfig(
            enabled=["kafka"],
            kafka=_KAFKA,
            transports={"kafka": {**_KAFKA, "bootstrap_servers": "explicit:9092"}},
        )
        assert config.transports["kafka"]["bootstrap_servers"] == "explicit:9092"

    def test_transports_entry_keeps_adapter_only_keys(self):
        """Raw entry is kept verbatim so adapter-only keys (ORCH component_mappings) survive."""
        config = BaseTransportConfig(
            enabled=["kafka"],
            transports={"kafka": {**_KAFKA, "component_mappings": {"ag": {}}}},
        )
        assert config.get_transport_config("kafka")["component_mappings"] == {"ag": {}}


class TestValidationAgreesWithLookup:
    """A gate that accepts what the lookup then returns None for moves the error one
    layer below the mistake — the adapter raises "configuration not found" at
    construction, pointing away from the config file that is wrong."""

    def test_a_typed_dict_field_no_lookup_can_resolve_is_rejected(self):
        class Sub(BaseTransportConfig):
            rest: dict | None = {"port": 8100}

        with pytest.raises(ValidationError, match="'rest' is enabled but not configured"):
            Sub(enabled=["rest"])

    def test_the_models_own_field_name_is_not_a_transport(self):
        with pytest.raises(ValidationError, match="'transports' is enabled but not configured"):
            BaseTransportConfig(enabled=["transports"])

    def test_a_typed_model_field_still_validates_and_resolves(self):
        class KafkaBlock(BaseModel):
            bootstrap_servers: str = "localhost:9092"

        class Sub(BaseTransportConfig):
            kafka: KafkaBlock | None = KafkaBlock()

        config = Sub(enabled=["kafka"], kafka={"bootstrap_servers": "broker:9092"})

        assert config.transports == {}
        assert config.get_transport_config("kafka") == {"bootstrap_servers": "broker:9092"}

    def test_everything_enabled_must_resolve(self):
        for name in _config().enabled:
            assert _config().get_transport_config(name) is not None
