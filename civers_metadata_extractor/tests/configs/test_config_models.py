"""Unit tests for Metadata Extractor configuration Pydantic models.

Only Metadata Extractor-specific behavior is tested here. Base model behaviour
(BaseDomainConfig, BaseKafkaConfig, BaseTransportConfig, BaseStorageConfig,
BaseAppConfig) and domain resolution (DomainResolutionMixin) are covered
exhaustively in civers_common/tests/.
"""

import pytest
from civers_common import ConfigurationError
from pydantic import ValidationError

from configs.models import (
    AppConfig,
    ConfigDataModel,
    DomainConfig,
    KafkaConfig,
    TransportConfig,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _kafka(**kwargs) -> KafkaConfig:
    defaults = {
        "bootstrap_servers": "localhost:29092",
        "topics": {"requests": "metadata.requests"},
    }
    return KafkaConfig(**{**defaults, **kwargs})


def _transport(**kwargs) -> TransportConfig:
    defaults = {"enabled": ["kafka"], "kafka": _kafka()}
    return TransportConfig(**{**defaults, **kwargs})


def _domain(name="arachne.dainst.org", **kwargs) -> DomainConfig:
    return DomainConfig(name=name, **kwargs)


# ── DomainConfig ──────────────────────────────────────────────────────────────


class TestDomainConfig:
    """ME DomainConfig adds input_source / extractor / mappings."""

    def test_input_source_defaults_to_html_document(self):
        assert _domain().input_source == "html_document"

    def test_accepts_extraction_fields(self):
        domain = _domain(
            input_source="json_file",
            extractor="jsonld",
            mappings={"name": "Title.title"},
        )
        assert domain.input_source == "json_file"
        assert domain.extractor == "jsonld"
        assert domain.mappings == {"name": "Title.title"}

    def test_mappings_without_extractor_rejected(self):
        with pytest.raises(ValidationError, match="mappings but no extractor"):
            _domain(mappings={"name": "Title.title"})

    def test_mappings_with_extractor_accepted(self):
        domain = _domain(extractor="jsonld", mappings={"name": "Title.title"})
        assert domain.extractor == "jsonld"

    def test_invalid_input_source_rejected(self):
        with pytest.raises(ValidationError):
            _domain(input_source="pdf")


# ── KafkaConfig ───────────────────────────────────────────────────────────────


class TestKafkaConfig:
    """ME KafkaConfig overrides only the consumer_group default."""

    def test_consumer_group_default(self):
        assert _kafka().consumer_group == "civers_metadata_extractor"

    def test_consumer_group_override(self):
        assert _kafka(consumer_group="custom").consumer_group == "custom"


# ── AppConfig ─────────────────────────────────────────────────────────────────


class TestAppConfig:
    """ME AppConfig — name default, storage helper, transport accessor."""

    def test_name_default(self):
        assert AppConfig().name == "metadata_extractor"

    def test_get_storage_config_returns_default_when_unset(self):
        cfg = AppConfig()
        assert cfg.storage is None
        assert cfg.get_storage_config().get_enabled_backends() == ["local_file"]

    def test_get_kafka_config_with_transport(self):
        cfg = AppConfig(transport=_transport())
        assert cfg.get_kafka_config() is cfg.transport.kafka

    def test_get_kafka_config_without_transport_returns_none(self):
        assert AppConfig().get_kafka_config() is None


# ── ConfigDataModel: transport sync ───────────────────────────────────────────


class TestConfigDataModelTransportSync:
    """ConfigDataModel transport-sync wiring (ME merges Kafka topics)."""

    def test_transport_sync_root_into_app(self):
        config = ConfigDataModel(app=AppConfig(), transport=_transport(), domains=[])
        assert config.app.transport is not None
        assert config.app.transport.kafka is config.transport.kafka

    def test_app_transport_synced_back_to_root(self):
        config = ConfigDataModel(app=AppConfig(transport=_transport()), domains=[])
        assert config.transport is not None
        assert config.transport.kafka is config.app.transport.kafka

    def test_topics_merged_when_both_present(self):
        app_transport = _transport(
            kafka=_kafka(topics={"started": "metadata.started"})
        )
        root_transport = _transport(
            kafka=_kafka(topics={"requests": "metadata.requests"})
        )
        config = ConfigDataModel(
            app=AppConfig(transport=app_transport),
            transport=root_transport,
            domains=[],
        )
        topics = config.app.transport.kafka.topics
        assert topics["started"] == "metadata.started"
        assert topics["requests"] == "metadata.requests"


# ── ConfigDataModel: domain resolution wiring ──────────────────────────────────


class TestConfigDataModelDomainResolution:
    """Confirms the shared DomainResolutionMixin is wired to ME DomainConfig."""

    def _config(self) -> ConfigDataModel:
        return ConfigDataModel(
            app=AppConfig(),
            domains=[
                _domain("arachne.dainst.org", extractor="jsonld", mappings={"a": "b"}),
                _domain("*.dainst.org"),
                _domain("default"),
            ],
        )

    def test_resolve_exact_returns_me_domain_config(self):
        domain = self._config().resolve_domain("arachne.dainst.org")
        assert isinstance(domain, DomainConfig)
        assert domain.mappings == {"a": "b"}

    def test_resolve_strips_port(self):
        domain = self._config().resolve_domain("arachne.dainst.org:8080")
        assert domain.name == "arachne.dainst.org"

    def test_resolve_wildcard_fallback(self):
        domain = self._config().resolve_domain("gazetteer.dainst.org")
        assert domain.name == "*.dainst.org"

    def test_resolve_default_fallback(self):
        domain = self._config().resolve_domain("unknown.example.com")
        assert domain.name == "default"

    def test_resolve_for_url(self):
        domain = self._config().resolve_domain_for_url("https://arachne.dainst.org/entity/1")
        assert domain.name == "arachne.dainst.org"

    def test_resolve_raises_when_no_match_and_no_default(self):
        config = ConfigDataModel(
            app=AppConfig(),
            domains=[_domain("arachne.dainst.org")],
        )
        with pytest.raises(ConfigurationError):
            config.resolve_domain("unknown.example.com")
