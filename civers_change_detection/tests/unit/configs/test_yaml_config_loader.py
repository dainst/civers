"""Unit tests for Change Detection YamlFileConfigLoader.

Base loader behaviour (env detection, deep merge, env-var expansion, CONFIG_DIR,
missing-file error, etc.) is covered exhaustively in civers_common/tests/test_yaml_loader.py.

Only Change Detection-specific behaviour is tested here:
  1. The default config directory points to this service's own configs/data/ folder.
  2. load() returns a valid CD ConfigDataModel from the real testing YAML files.
  3. Isolated load with CD-specific model structure works end-to-end.
"""

import inspect
from pathlib import Path


from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel


class TestYamlFileConfigLoader:

    def test_config_dir_is_set_to_default(self):
        """Default config_dir resolves to <loader_module_dir>/data/."""
        loader = YamlFileConfigLoader()
        expected = Path(inspect.getfile(YamlFileConfigLoader)).parent / "data"
        assert loader.config_dir == expected
        assert loader.defaults_dir == expected / "defaults"
        assert loader.environments_dir == expected / "environments"

    def test_load_testing_environment_returns_valid_config_data_model(self):
        """load() returns the CD ConfigDataModel with correctly merged testing config."""
        loader = YamlFileConfigLoader()
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

    def test_load_isolated_config_dir(self, tmp_path):
        """Isolated load: defaults + testing.yaml merge into a valid CD ConfigDataModel."""
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
    webpage_types: dynamic
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
