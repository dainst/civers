"""Unit tests for the configuration loader."""

import inspect
from pathlib import Path

import pytest

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel


class TestYamlFileConfigLoader:
    def test_config_dir_is_set_to_default(self, monkeypatch):
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")
        loader = YamlFileConfigLoader()
        assert isinstance(loader.config_dir, Path)
        assert loader.config_dir == Path(inspect.getfile(YamlFileConfigLoader)).parent / "data"
        assert loader.defaults_dir == loader.config_dir / "defaults"
        assert loader.environments_dir == loader.config_dir / "environments"

    def test_config_dir_is_set_to_env_var(self, monkeypatch):
        monkeypatch.setenv("CONFIG_DIR", "/tmp")
        loader = YamlFileConfigLoader()
        assert loader.config_dir == Path("/tmp")
        assert loader.defaults_dir == Path("/tmp/defaults")
        assert loader.environments_dir == Path("/tmp/environments")

    def test_detect_testing_environment_from_pytest(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_something")
        monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
        loader = YamlFileConfigLoader()
        assert loader.environment == "testing"

    def test_default_environment_is_development(self, monkeypatch):
        monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        loader = YamlFileConfigLoader()
        assert loader.environment == "development"

    def test_deep_merge(self):
        loader = YamlFileConfigLoader()
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99, "e": 5}}
        merged = loader._deep_merge(base, override)
        assert merged == {"a": 1, "b": {"c": 99, "d": 3, "e": 5}}

    def test_expand_env_vars(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_VAR", "hello")
        loader = YamlFileConfigLoader()
        result = loader._expand_env_vars({"key": "${MY_TEST_VAR:-world}"})
        assert result == {"key": "hello"}

    def test_expand_env_vars_default(self, monkeypatch):
        monkeypatch.delenv("MY_MISSING_VAR", raising=False)
        loader = YamlFileConfigLoader()
        result = loader._expand_env_vars({"key": "${MY_MISSING_VAR:-fallback}"})
        assert result == {"key": "fallback"}

    def test_load_yaml_file(self, tmp_path):
        dummy_yaml = """
        app:
            name: test_app
            version: 0.1.0
        """
        file_path = tmp_path / "test_config.yaml"
        file_path.write_text(dummy_yaml)

        loader = YamlFileConfigLoader()
        result = loader._load_yaml_file(file_path)
        assert result == {"app": {"name": "test_app", "version": "0.1.0"}}

    def test_load_testing_environment_returns_valid_config_data_model(self, monkeypatch):
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")
        loader = YamlFileConfigLoader()
        assert loader.environment == "testing"

        config = loader.load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "change_detection_system"
        assert config.app.environment == "testing"

        kafka = config.app.get_kafka_config()
        assert kafka is not None
        assert kafka.bootstrap_servers == "localhost:29092"
        assert kafka.consumer_group == "change_detection_group_test"
        assert "requests" in kafka.topics

        assert len(config.domains) >= 1
        arachne = config.resolve_domain_for_url("https://arachne.test.dainst.org/item/1")
        assert arachne.change_detection.detection_strategy == "css_selector"

    def test_load_isolated_config_dir(self, tmp_path, monkeypatch):
        """Loader merges defaults + testing.yaml into a valid ConfigDataModel."""
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")

        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "app.yaml").write_text(
            """
            app:
              name: isolated_app
              version: 1.0.0
            domains:
              - name: test.local
                enabled: true
                change_detection:
                  detection_strategy: css_selector
                  comparison_algorithm: simple_text
                webpage_types: "dynamic"
            """
        )
        (defaults_dir / "kafka.yaml").write_text(
            """
            app:
              transport:
                enabled:
                  - kafka
                kafka:
                  bootstrap_servers: broker:9092
                  topics:
                    requests: test.requests
                    completed: test.completed
            """
        )

        env_dir = tmp_path / "environments"
        env_dir.mkdir()
        (env_dir / "testing.yaml").write_text(
            """
            app:
              environment: testing
              transport:
                kafka:
                  consumer_group: isolated_test_group
            """
        )

        config = YamlFileConfigLoader(config_dir=tmp_path).load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "isolated_app"
        assert config.app.environment == "testing"
        assert config.app.get_kafka_config().consumer_group == "isolated_test_group"

        domain = config.resolve_domain_for_url("https://test.local/page")
        assert domain.change_detection.detection_strategy == "css_selector"
