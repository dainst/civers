"""Unit tests for Archive Generator configuration Pydantic models.

Only AG-specific behavior is tested here. Base model behaviour
(BaseKafkaConfig, BaseTransportConfig, BaseStorageConfig, BaseAppConfig)
is covered exhaustively in civers_common/tests/.
"""

import pytest
from pydantic import ValidationError

from configs.models import (
    AppConfig,
    ConfigDataModel,
    DomainConfig,
    GeneratorConfig,
    KafkaConfig,
    StorageConfig,
    TransportConfig,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _storage(**kwargs) -> StorageConfig:
    defaults = {
        "enabled": ["local_file"],
        "backends": {"local_file": {"base_path": "archives"}},
    }
    return StorageConfig(**{**defaults, **kwargs})


def _transport(**kwargs) -> TransportConfig:
    defaults = {
        "enabled": ["kafka"],
        "kafka": KafkaConfig(
            bootstrap_servers="localhost:9092",
            topics={"requests": "archive.requests"},
            consumer_group="test-group",
        ),
    }
    return TransportConfig(**{**defaults, **kwargs})


def _app(**kwargs) -> AppConfig:
    defaults = {
        "archive_directory": "/tmp/archives",
        "storage": _storage(),
    }
    return AppConfig(**{**defaults, **kwargs})


# ── DomainConfig ──────────────────────────────────────────────────────────────


class TestDomainConfig:
    """AG DomainConfig adds a required `generators` list."""

    def test_requires_at_least_one_generator(self):
        with pytest.raises(ValidationError, match="at least one generator"):
            DomainConfig(name="example.com", generators=[], webpage_types="dynamic")

    def test_accepts_single_generator(self):
        domain = DomainConfig(
            name="example.com",
            generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
            webpage_types="dynamic",
        )
        assert len(domain.generators) == 1
        assert domain.generators[0].name == "scoop"

    def test_accepts_multiple_generators(self):
        domain = DomainConfig(
            name="example.com",
            generators=[
                GeneratorConfig(name="scoop", artifacts=["warc", "screenshot"]),
                GeneratorConfig(name="singlefile", artifacts=["singlefile"]),
            ],
            webpage_types="dynamic",
        )
        assert len(domain.generators) == 2

    def test_generator_config_stores_artifacts(self):
        gen = GeneratorConfig(name="scoop", artifacts=["warc", "screenshot", "dom-snapshot"])
        assert gen.artifacts == ["warc", "screenshot", "dom-snapshot"]


# ── AppConfig ─────────────────────────────────────────────────────────────────


class TestAppConfig:
    """AG AppConfig — archive_directory, scoop/singlefile settings, storage helpers."""

    def test_defaults(self):
        cfg = _app()
        assert cfg.name == "archive_generator"
        assert cfg.scoop_cli_command == "scoop"
        assert cfg.scoop_timeout_sec == 120
        assert cfg.scoop_extra_args is None
        assert cfg.ssrf_protection_enabled is True

    def test_archive_directory_is_required(self):
        with pytest.raises(ValidationError):
            AppConfig(storage=_storage())

    def test_storage_is_required(self):
        with pytest.raises(ValidationError):
            AppConfig(archive_directory="/tmp/archives")

    def test_get_storage_config_returns_storage(self):
        storage = _storage()
        cfg = _app(storage=storage)
        assert cfg.get_storage_config() is storage

    def test_get_kafka_config_with_transport(self):
        transport = _transport()
        cfg = _app(transport=transport)
        assert cfg.get_kafka_config() == transport.kafka

    def test_get_kafka_config_without_transport_returns_none(self):
        cfg = _app()
        assert cfg.get_kafka_config() is None

    def test_scoop_extra_args_accepts_list(self):
        cfg = _app(scoop_extra_args=["--log-level", "info", "--no-sandbox"])
        assert cfg.scoop_extra_args == ["--log-level", "info", "--no-sandbox"]


# ── ConfigDataModel ───────────────────────────────────────────────────────────


class TestConfigDataModelConstruction:
    """ConfigDataModel structure and validators."""

    def test_transport_sync_root_into_app(self):
        """Root-level `transport` is synced into `app.transport` when not set."""
        config = ConfigDataModel(
            domains=[
                DomainConfig(
                    name="example.com",
                    generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
                    webpage_types="dynamic",
                )
            ],
            app=_app(),
            transport=_transport(),
        )
        assert config.app.transport is not None
        assert config.app.transport.kafka is config.transport.kafka

    def test_app_transport_takes_precedence_over_root(self):
        """If app.transport is already set, root transport does not overwrite it."""
        app_transport = _transport()
        root_transport = _transport()
        config = ConfigDataModel(
            domains=[
                DomainConfig(
                    name="example.com",
                    generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
                    webpage_types="dynamic",
                )
            ],
            app=_app(transport=app_transport),
            transport=root_transport,
        )
        assert config.app.transport is app_transport

    def test_domain_with_missing_generators_rejected(self):
        """Domain config without generators should be rejected at the domain level."""
        with pytest.raises(ValidationError):
            DomainConfig(name="example.com", generators=[], webpage_types="dynamic")


# ── YAML integration ──────────────────────────────────────────────────────────


class TestConfigDataModelFromTestingYaml:
    """ConfigDataModel built from defaults + environments/testing.yaml."""

    def test_testing_config_is_config_data_model(self, testing_config):
        assert isinstance(testing_config, ConfigDataModel)

    def test_app_name_from_defaults(self, testing_config):
        assert testing_config.app.name == "archive_generator"

    def test_testing_environment_set(self, testing_config):
        assert testing_config.app.environment == "testing"

    def test_domains_loaded_with_generators(self, testing_config):
        assert len(testing_config.domains) > 0
        for domain in testing_config.domains:
            assert len(domain.generators) > 0

    def test_known_domain_present(self, testing_config):
        names = {d.name for d in testing_config.domains}
        assert "example.com" in names

    def test_transport_synced_to_app(self, testing_config):
        assert testing_config.app.transport is not None
        assert testing_config.transport is not None
        assert testing_config.app.transport.kafka is testing_config.transport.kafka

    def test_storage_config_has_enabled_backends(self, testing_config):
        storage = testing_config.app.get_storage_config()
        assert len(storage.get_enabled_backends()) > 0
