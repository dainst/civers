"""Unit tests for Orchestrator YamlFileConfigLoader and domain resolution.

Base loader behaviour (env detection, deep merge, env-var expansion, CONFIG_DIR,
missing-file error, etc.) is covered exhaustively in
civers_common/tests/test_yaml_loader.py.

Only Orchestrator-specific behaviour is tested here:
  1. The default config directory points to this service's own configs/data/ folder.
  2. load() returns a valid ORCH ConfigDataModel from the real testing YAML files.
  3. Isolated load with ORCH-specific model structure works end-to-end.
  4. Domain -> workflow resolution (exact / wildcard / default) via the shared
     ``civers_common.DomainResolutionMixin``.
  5. Workflow step / dependency wiring.
"""

import inspect
from pathlib import Path

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel


class TestYamlFileConfigLoader:
    """Loader wiring specific to the Orchestrator service."""

    def test_config_dir_is_set_to_default(self):
        """Default config_dir resolves to <loader_module_dir>/data/."""
        loader = YamlFileConfigLoader()
        expected = Path(inspect.getfile(YamlFileConfigLoader)).parent / "data"
        assert loader.config_dir == expected
        assert loader.defaults_dir == expected / "defaults"
        assert loader.environments_dir == expected / "environments"

    def test_load_testing_environment_returns_valid_config_data_model(self):
        """load() returns the ORCH ConfigDataModel with merged testing config."""
        config = YamlFileConfigLoader().load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.environment == "testing"
        assert config.transport.kafka.bootstrap_servers == "localhost:29092"
        assert len(config.workflows) >= 1
        assert len(config.domains) >= 1
        assert all(d.workflow for d in config.domains)

    def test_load_isolated_config_dir(self, tmp_path, monkeypatch):
        """Isolated load: defaults + testing.yaml merge into a valid ORCH model."""
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "app.yaml").write_text(
            """
app:
  name: isolated_orch
  version: 1.0.0
"""
        )
        (defaults_dir / "kafka.yaml").write_text(
            """
transport:
  enabled:
    - kafka
  kafka:
    bootstrap_servers: broker:9092
    consumer:
      group_id: isolated_default_group
      auto_offset_reset: earliest
    producer:
      acks: all
      retries: 3
    topics:
      orchestrator_requests: orchestrator.requests
      orchestrator_status: orchestrator.status
      orchestrator_completed: orchestrator.completed
      orchestrator_failed: orchestrator.failed
"""
        )
        (defaults_dir / "domains.yaml").write_text(
            """
domains:
  - name: default
    workflow: isolated_workflow
"""
        )
        (defaults_dir / "workflows.yaml").write_text(
            """
workflows:
  - name: isolated_workflow
    description: Isolated test workflow
    steps:
      - name: step1
        component: comp1
        input_schema: Step1Request
        output_schemas:
          success: Step1Completed
          failure: Step1Failed
        depends_on: []
        timeout_seconds: 60
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
    consumer:
      group_id: isolated_test_group
"""
        )

        config = YamlFileConfigLoader(config_dir=tmp_path).load()

        assert isinstance(config, ConfigDataModel)
        assert config.app.name == "isolated_orch"
        assert config.app.environment == "testing"
        assert config.transport.kafka.consumer.group_id == "isolated_test_group"
        assert config.transport.kafka.bootstrap_servers == "broker:9092"


class TestDomainWorkflowResolution:
    """Domain -> workflow mapping via the shared DomainResolutionMixin."""

    def test_exact_match(self, test_config: ConfigDataModel):
        workflow = test_config.get_workflow_for_domain("arachne.dainst.org")
        assert workflow is not None
        assert workflow.name == "archaeology_workflow"

    def test_wildcard_match(self, test_config: ConfigDataModel):
        workflow = test_config.get_workflow_for_domain("subsite.dainst.org")
        assert workflow is not None
        assert workflow.name == "dainst_workflow"

    def test_default_fallback(self, test_config: ConfigDataModel):
        workflow = test_config.get_workflow_for_domain("unknown.example.org")
        assert workflow is not None
        assert workflow.name == "simple_workflow"

    def test_workflow_step_dependencies(self, test_config: ConfigDataModel):
        workflow = test_config.get_workflow_by_name("archaeology_workflow")
        assert workflow is not None
        step_names = [s.name for s in workflow.steps]
        assert step_names == ["archive_generation", "metadata_extraction"]
        assert workflow.steps[1].depends_on == ["archive_generation"]
