"""Unit tests for Archive Generator YamlFileConfigLoader.

Base loader behaviour (env detection, deep merge, env-var expansion, CONFIG_DIR,
missing-file error, etc.) is covered exhaustively in civers_common/tests/test_yaml_loader.py.

Only Archive Generator-specific behaviour is tested here:
  1. The default config directory points to this service's own configs/data/ folder.
  2. load() returns a valid AG ConfigDataModel from the real testing YAML files.
  3. Isolated load with AG-specific model structure works end-to-end.
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
        """load() returns the AG ConfigDataModel with correctly merged testing config."""
        loader = YamlFileConfigLoader()
        config = loader.load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "archive_generator"
        assert config.app.environment == "testing"
        assert len(config.domains) >= 1
        assert all(len(d.generators) > 0 for d in config.domains)
        transport = config.app.transport
        assert transport is not None
        assert transport.kafka is not None

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
    enabled:
      - local_file
    backends:
      local_file:
        base_path: archives
domains:
  - name: test.local
    generators:
      - name: scoop
        artifacts: [warc]
    webpage_types: dynamic
"""
        )
        # AG puts transport at root level; the sync_transport_config validator
        # copies it into app.transport when app.transport is not explicitly set.
        (defaults_dir / "kafka.yaml").write_text(
            """
transport:
  enabled:
    - kafka
  kafka:
    bootstrap_servers: broker:9092
    consumer_group: isolated_default_group
    topics:
      requests: archive.requests
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
        assert config.app.name == "isolated_ag"
        assert config.app.environment == "testing"
        assert config.app.get_kafka_config().consumer_group == "isolated_test_group"
        domain = next(d for d in config.domains if d.name == "test.local")
        assert domain.generators[0].name == "scoop"
