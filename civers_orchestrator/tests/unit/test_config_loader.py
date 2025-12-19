"""Unit tests for configuration loading."""

import os
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel


@pytest.fixture(autouse=True)
def unset_config_environment():
    """Unset CONFIG_ENVIRONMENT for config loader tests.

    These tests use temporary config directories and should not be affected
    by the global force_testing_environment fixture from tests/conftest.py.
    """
    old_env = os.environ.pop("CONFIG_ENVIRONMENT", None)
    yield
    if old_env is not None:
        os.environ["CONFIG_ENVIRONMENT"] = old_env


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create temporary configuration directory structure."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()
    return tmp_path


@pytest.fixture
def base_config_files(temp_config_dir: Path) -> Dict[str, Path]:
    """Create base configuration files."""
    defaults_dir = temp_config_dir / "defaults"

    # app.yaml
    app_config = {"app": {"name": "civers_orchestrator", "version": "1.0.0", "environment": "test"}}
    app_file = defaults_dir / "app.yaml"
    with open(app_file, "w") as f:
        yaml.dump(app_config, f)

    # kafka.yaml
    kafka_config = {
        "transport": {
            "enabled": ["kafka"],
            "kafka": {
                "bootstrap_servers": "localhost:29092",
                "consumer": {"group_id": "civers_orchestrator", "auto_offset_reset": "earliest"},
                "producer": {"acks": "all", "retries": 3},
                "topics": {
                    "orchestrator_requests": "orchestrator.requests",
                    "orchestrator_status": "orchestrator.status",
                    "orchestrator_completed": "orchestrator.completed",
                    "orchestrator_failed": "orchestrator.failed",
                },
            },
        }
    }
    kafka_file = defaults_dir / "kafka.yaml"
    with open(kafka_file, "w") as f:
        yaml.dump(kafka_config, f)

    # domains.yaml
    domains_config = {
        "domains": [
            {"name": "arachne.dainst.org", "workflow": "archaeology_workflow"},
            {"name": "*.dainst.org", "workflow": "standard_dainst_workflow"},
            {"name": "default", "workflow": "standard_archive_workflow"},
        ]
    }
    domains_file = defaults_dir / "domains.yaml"
    with open(domains_file, "w") as f:
        yaml.dump(domains_config, f)

    # workflows.yaml
    workflows_config = {
        "workflows": [
            {
                "name": "standard_archive_workflow",
                "description": "Standard web page archiving workflow",
                "steps": [
                    {
                        "name": "archive_generation",
                        "component": "archive_generator",
                            "depends_on": [],
                                                "input_schema": "ArchiveRequest",
                        "output_schemas": {
                            "success": "ArchiveCompleted",
                            "failure": "ArchiveFailed",
                        },
                        "timeout_seconds": 300,
                    }
                ],
            },
            {
                "name": "archaeology_workflow",
                "description": "Specialized workflow for archaeological content",
                "steps": [
                    {
                        "name": "archive_generation",
                        "component": "archive_generator",
                            "depends_on": [],
                                                "input_schema": "ArchiveRequest",
                        "output_schemas": {
                            "success": "ArchiveCompleted",
                            "failure": "ArchiveFailed",
                        },
                        "timeout_seconds": 600,
                    }
                ],
            },
            {
                "name": "standard_dainst_workflow",
                "description": "Standard DAINST workflow",
                "steps": [
                    {
                        "name": "archive_generation",
                        "component": "archive_generator",
                            "depends_on": [],
                                                "input_schema": "ArchiveRequest",
                        "output_schemas": {
                            "success": "ArchiveCompleted",
                            "failure": "ArchiveFailed",
                        },
                        "timeout_seconds": 300,
                    }
                ],
            },
        ]
    }
    workflows_file = defaults_dir / "workflows.yaml"
    with open(workflows_file, "w") as f:
        yaml.dump(workflows_config, f)

    return {
        "app": app_file,
        "kafka": kafka_file,
        "domains": domains_file,
        "workflows": workflows_file,
    }


def test_load_default_configuration(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test loading default configuration."""
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    assert isinstance(config, ConfigDataModel)
    assert config.app.name == "civers_orchestrator"
    assert config.app.version == "1.0.0"
    assert config.transport.kafka.bootstrap_servers == "localhost:29092"


def test_load_development_environment(
    temp_config_dir: Path, base_config_files: Dict[str, Path]
) -> None:
    """Test loading development environment configuration."""
    # Create development override
    env_dir = temp_config_dir / "environments"
    dev_config = {"app": {"environment": "development"}}
    with open(env_dir / "development.yaml", "w") as f:
        yaml.dump(dev_config, f)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir, environment="development")
    config = loader.load()

    assert config.app.environment == "development"


def test_load_testing_environment(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test loading testing environment configuration."""
    # Create testing override
    env_dir = temp_config_dir / "environments"
    test_config = {
        "app": {"environment": "testing"},
        "transport": {"kafka": {"bootstrap_servers": "localhost:29093"}},
    }
    with open(env_dir / "testing.yaml", "w") as f:
        yaml.dump(test_config, f)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir, environment="testing")
    config = loader.load()

    assert config.app.environment == "testing"
    assert config.transport.kafka.bootstrap_servers == "localhost:29093"


def test_load_docker_environment(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test loading docker environment configuration."""
    # Create docker override
    env_dir = temp_config_dir / "environments"
    docker_config = {
        "app": {"environment": "docker"},
        "transport": {"kafka": {"bootstrap_servers": "broker:9092"}},
    }
    with open(env_dir / "docker.yaml", "w") as f:
        yaml.dump(docker_config, f)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir, environment="docker")
    config = loader.load()

    assert config.app.environment == "docker"
    assert config.transport.kafka.bootstrap_servers == "broker:9092"


def test_environment_override_merging(
    temp_config_dir: Path, base_config_files: Dict[str, Path]
) -> None:
    """Test that environment overrides properly merge with defaults."""
    # Create environment override that only changes one value
    env_dir = temp_config_dir / "environments"
    override_config = {
        "transport": {
            "kafka": {
                "consumer": {"group_id": "civers_orchestrator_dev"},
            }
        }
    }
    with open(env_dir / "development.yaml", "w") as f:
        yaml.dump(override_config, f)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir, environment="development")
    config = loader.load()

    # Override should be applied
    assert config.transport.kafka.consumer.group_id == "civers_orchestrator_dev"
    # Other values should remain from defaults
    assert config.transport.kafka.bootstrap_servers == "localhost:29092"
    assert config.transport.kafka.consumer.auto_offset_reset == "earliest"


def test_domain_workflow_mapping(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test domain-to-workflow mapping."""
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    # Test exact match
    workflow = config.get_workflow_for_domain("arachne.dainst.org")
    assert workflow is not None
    assert workflow.name == "archaeology_workflow"

    # Test wildcard match
    workflow = config.get_workflow_for_domain("field.dainst.org")
    assert workflow is not None
    assert workflow.name == "standard_dainst_workflow"

    # Test default
    workflow = config.get_workflow_for_domain("example.com")
    assert workflow is not None
    assert workflow.name == "standard_archive_workflow"


def test_workflow_step_validation(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test workflow step dependency validation."""
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    workflow = config.get_workflow_by_name("standard_archive_workflow")
    assert workflow is not None
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "archive_generation"
    assert workflow.steps[0].timeout_seconds == 300


def test_invalid_config_raises_error(temp_config_dir: Path) -> None:
    """Test that invalid configuration raises validation error."""
    defaults_dir = temp_config_dir / "defaults"

    # Create invalid config (missing required fields)
    invalid_config = {"app": {"name": "test"}}
    with open(defaults_dir / "app.yaml", "w") as f:
        yaml.dump(invalid_config, f)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)

    with pytest.raises(Exception):  # Could be ValidationError or other
        loader.load()


def test_environment_auto_detection_from_env_var(
    temp_config_dir: Path, base_config_files: Dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test environment auto-detection from CONFIG_ENVIRONMENT variable."""
    # Create docker environment file
    env_dir = temp_config_dir / "environments"
    docker_config = {"app": {"environment": "docker"}}
    with open(env_dir / "docker.yaml", "w") as f:
        yaml.dump(docker_config, f)

    # Test 1: CONFIG_ENVIRONMENT variable (highest priority)
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "docker")
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()
    assert config.app.environment == "docker"

    # Test 2: CONFIG_ENVIRONMENT takes precedence over PYTEST_CURRENT_TEST
    testing_config = {"app": {"environment": "testing"}}
    with open(env_dir / "testing.yaml", "w") as f:
        yaml.dump(testing_config, f)

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "some_test")
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()
    assert config.app.environment == "docker"  # CONFIG_ENVIRONMENT still has precedence

    # Test 3: PYTEST_CURRENT_TEST detection after unsetting CONFIG_ENVIRONMENT
    monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()
    assert config.app.environment == "testing"  # Now detects testing environment

    # Test 4: Docker detection via /.dockerenv file (higher priority than PYTEST)
    # Unset PYTEST_CURRENT_TEST first
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    # Mock os.path.exists to simulate /.dockerenv presence
    import os as os_module
    original_exists = os_module.path.exists

    def mock_exists(path: str) -> bool:
        if path == "/.dockerenv":
            return True
        return original_exists(path)

    monkeypatch.setattr(os_module.path, "exists", mock_exists)

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()
    assert config.app.environment == "docker"  # Detects docker via /.dockerenv

def test_workflow_with_dependencies(temp_config_dir: Path, base_config_files: Dict[str, Path]) -> None:
    """Test workflow with step dependencies."""
    # Add a workflow with dependencies
    defaults_dir = temp_config_dir / "defaults"
    workflow_with_deps = {
        "workflows": [
            {
                "name": "test_workflow",
                "description": "Test workflow with dependencies",
                "steps": [
                    {
                        "name": "step1",
                        "component": "component1",
                            "depends_on": [],
                                                "input_schema": "Step1Request",
                        "output_schemas": {"success": "Step1Completed", "failure": "Step1Failed"},
                        "timeout_seconds": 60,
                    },
                    {
                        "name": "step2",
                        "component": "component2",
                        "depends_on": ["step1"],
                                                "input_schema": "Step2Request",
                        "output_schemas": {"success": "Step2Completed", "failure": "Step2Failed"},
                        "timeout_seconds": 60,
                    },
                ],
            }
        ],
        "domains": [{"name": "default", "workflow": "test_workflow"}],
    }

    # Update workflows file
    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump({"workflows": workflow_with_deps["workflows"]}, f)

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": workflow_with_deps["domains"]}, f)

    # Load minimal app and kafka configs
    with open(defaults_dir / "app.yaml", "w") as f:
        yaml.dump({"app": {"name": "test", "version": "1.0.0", "environment": "test"}}, f)

    with open(defaults_dir / "kafka.yaml", "w") as f:
        yaml.dump(
            {
                "transport": {
                    "enabled": ["kafka"],
                    "kafka": {
                        "bootstrap_servers": "localhost:29092",
                        "consumer": {"group_id": "test", "auto_offset_reset": "earliest"},
                        "producer": {"acks": "all", "retries": 3},
                        "topics": {
                            "orchestrator_requests": "test.requests",
                            "orchestrator_status": "test.status",
                            "orchestrator_completed": "test.completed",
                            "orchestrator_failed": "test.failed",
                        },
                    },
                }
            },
            f,
        )

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    workflow = config.get_workflow_by_name("test_workflow")
    assert workflow is not None
    assert len(workflow.steps) == 2
    assert workflow.steps[1].depends_on == ["step1"]

def test_loading_environment_with_new_environment_file(
    temp_config_dir: Path, base_config_files: Dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test loading configuration with a new environment file."""
    # Create a new environment override
    env_dir = temp_config_dir / "environments"
    new_env_config = {
        "app": {"environment": "staging"},
        "transport": {"kafka": {"bootstrap_servers": "staging-broker:9092"}},
    }
    with open(env_dir / "staging.yaml", "w") as f:
        yaml.dump(new_env_config, f)
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "staging")

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    assert config.app.environment == "staging"
    assert config.transport.kafka.bootstrap_servers == "staging-broker:9092"

# Note: Environment validation tests (missing environment files, explicit vs auto-detected)
# have been consolidated into tests/unit/test_environment_validation.py to avoid duplication