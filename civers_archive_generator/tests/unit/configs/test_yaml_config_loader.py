"""Check the archive YAML catalog and resulting service configuration.

Shared loader tests live in civers_common/tests/config_tests/test_yaml_loader.py.
"""

import inspect
from pathlib import Path

import pytest
from civers_common.configs.models import BaseKafkaConfig
from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel


@pytest.mark.parametrize("environment", ["development", "docker"])
def test_default_catalog_uses_supported_generators_and_artifacts(
    monkeypatch, environment
):
    """Validate deployed capture choices through the service's configuration model."""
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP_ID", "catalog-test")
    monkeypatch.setenv("CIVERS_API_URL", "http://localhost:8000")
    config_dir = (
        Path(__file__).resolve().parents[4] / "configs" / "data" / "archive_generator"
    )
    config = YamlFileConfigLoader(config_dir=config_dir, environment=environment).load()
    choices = {tuple(g.name for g in domain.generators) for domain in config.domains}
    assert {"scoop", "browsertrix", "singlefile"} == {
        generator for choice in choices for generator in choice
    }
    assert any(len(choice) > 1 for choice in choices)


@pytest.mark.parametrize("environment,acks", [("docker", "all"), ("testing", "all")])
def test_shared_yaml_uses_explicit_kafka_settings(monkeypatch, environment, acks):
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP_ID", "archive-config-test")
    monkeypatch.setenv("KAFKA_PRODUCER_ACKS", "1")
    monkeypatch.setenv("CIVERS_API_URL", "http://localhost:8000")
    config_dir = (
        Path(__file__).resolve().parents[4] / "configs" / "data" / "archive_generator"
    )
    config = YamlFileConfigLoader(config_dir=config_dir, environment=environment).load()
    kafka = BaseKafkaConfig.model_validate(
        config.transport.get_transport_config("kafka")
    )
    assert kafka.producer_acks == acks
    assert kafka.consumer_group == "archive-config-test"
    assert kafka.consumer_enable_auto_commit is False
    assert kafka.consumer is None
    assert kafka.producer is None


class TestYamlFileConfigLoader:
    def test_cli_environment_uses_root_level_transport(self, monkeypatch):
        """Load CLI settings from the root transport section."""
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "cli")

        config = YamlFileConfigLoader().load()

        assert config.transport.enabled == ["cli"]
        assert config.transport.get_transport_config("cli") == {}
        storage = config.app.get_storage_config()
        assert storage.get_enabled_backends() == []

    def test_restapi_environment_uses_root_level_transport(self, monkeypatch):
        """Load REST settings from the root transport section."""
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "restapi")

        config = YamlFileConfigLoader().load()

        assert config.transport.enabled == ["restapi"]
        assert config.transport.get_transport_config("restapi")["port"] == 8100

    def test_config_dir_is_set_to_default(self):
        """Default config_dir resolves to the shared archive generator catalog."""
        loader = YamlFileConfigLoader()
        expected = (
            Path(inspect.getfile(YamlFileConfigLoader)).parents[2]
            / "configs"
            / "data"
            / "archive_generator"
        )
        assert loader.config_dir == expected
        assert loader.defaults_dir == expected / "defaults"
        assert loader.environments_dir == expected / "environments"

    def test_load_testing_environment_returns_valid_config_data_model(self):
        """load() returns the AG ConfigDataModel with correctly merged testing config."""
        loader = YamlFileConfigLoader()
        config = loader.load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "archive_generator"
        assert config.app.environment == "testing"
        assert len(config.domains) >= 1
        assert all(len(d.generators) > 0 for d in config.domains)
        assert "example.com" in {domain.name for domain in config.domains}
        assert "kafka" in config.transport.enabled
        assert config.transport.get_transport_config("kafka") is not None
        assert config.app.get_storage_config().get_enabled_backends() == []

    def test_load_isolated_config_dir(self, tmp_path):
        """Isolated load: defaults + testing.yaml merge into a valid AG ConfigDataModel."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "app.yaml").write_text(
            """
app:
  name: isolated_ag
  version: 1.0.0
  archive_directory: /tmp/archives
  storage:
    enabled: []
    backends: {}
domains:
  - name: test.local
    generators:
      - name: scoop
        artifacts: [warc]
    webpage_types: dynamic
"""
        )
        # AG puts transport at root level (the only location).
        (defaults_dir / "kafka.yaml").write_text(
            """
transport:
  enabled:
    - kafka
  transports:
    kafka:
      bootstrap_servers: broker:9092
      consumer_group: isolated_default_group
      topics:
        archive_requests: archive.requests
"""
        )

        env_dir = tmp_path / "environments"
        env_dir.mkdir()
        (env_dir / "testing.yaml").write_text(
            """
app:
  environment: testing
transport:
  transports:
    kafka:
      consumer_group: isolated_test_group
"""
        )

        config = YamlFileConfigLoader(config_dir=tmp_path, environment="testing").load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "isolated_ag"
        assert config.app.environment == "testing"
        kafka = config.transport.get_transport_config("kafka")
        assert kafka["consumer_group"] == "isolated_test_group"
        assert kafka["bootstrap_servers"] == "broker:9092"
        assert kafka["topics"]["archive_requests"] == "archive.requests"
        domain = next(d for d in config.domains if d.name == "test.local")
        assert domain.generators[0].name == "scoop"
