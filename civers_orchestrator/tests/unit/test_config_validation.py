"""Unit tests for configuration validation edge cases.

Updated for Task 13: Transport-agnostic workflow models.
All tests now use the new format without Kafka-specific fields.
"""

import os
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from configs.loaders import YamlFileConfigLoader


@pytest.fixture(autouse=True)
def unset_config_environment():
    """Unset CONFIG_ENVIRONMENT for config validation tests.

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
def minimal_valid_config(temp_config_dir: Path) -> Path:
    """Create minimal valid configuration (transport-agnostic format)."""
    defaults_dir = temp_config_dir / "defaults"

    # Minimal app config
    with open(defaults_dir / "app.yaml", "w") as f:
        yaml.dump({"app": {"name": "test", "version": "1.0.0", "environment": "test"}}, f)

    # Minimal kafka config
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

    return temp_config_dir


def test_duplicate_step_names(minimal_valid_config: Path) -> None:
    """Test that duplicate step names within a workflow are caught."""
    defaults_dir = minimal_valid_config / "defaults"

    # Create workflow with duplicate step names (transport-agnostic format)
    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            },
                            {
                                "name": "step1",  # Duplicate!
                                "component": "comp2",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            },
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    # Should raise ValidationError for duplicate step names
    with pytest.raises(ValidationError, match="must have unique names"):
        loader.load()


def test_circular_dependency_simple(minimal_valid_config: Path) -> None:
    """Test detection of simple circular dependency."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "depends_on": ["step2"],  # Points to step2 (list format)
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "timeout_seconds": 60,
                            },
                            {
                                "name": "step2",
                                "component": "comp2",
                                "depends_on": ["step1"],  # Points back to step1!
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "timeout_seconds": 60,
                            },
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    # Should raise ValidationError for circular dependency
    with pytest.raises(ValidationError, match="Circular dependency detected"):
        loader.load()


def test_empty_workflow_name(minimal_valid_config: Path) -> None:
    """Test that empty workflow names are rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "",  # Empty name
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        loader.load()


def test_empty_step_name(minimal_valid_config: Path) -> None:
    """Test that empty step names are rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "",  # Empty name
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        loader.load()


def test_empty_schema_names(minimal_valid_config: Path) -> None:
    """Test that empty schema names are rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "",  # Empty schema
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        loader.load()


def test_negative_timeout(minimal_valid_config: Path) -> None:
    """Test that negative timeouts are rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": -1,  # Negative!
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        loader.load()


def test_zero_timeout(minimal_valid_config: Path) -> None:
    """Test that zero timeouts are rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 0,  # Zero!
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        loader.load()


def test_empty_workflows_list(minimal_valid_config: Path) -> None:
    """Test that empty workflows list is rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump({"workflows": []}, f)  # Empty!

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError):
        loader.load()


def test_missing_output_schemas(minimal_valid_config: Path) -> None:
    """Test that missing output_schemas is rejected."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "test_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                # Missing output_schemas!
                                "depends_on": [],
                                "timeout_seconds": 60,
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump({"domains": [{"name": "default", "workflow": "test_workflow"}]}, f)

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="output_schemas"):
        loader.load()


def test_domain_references_nonexistent_workflow(minimal_valid_config: Path) -> None:
    """Test that domain referencing non-existent workflow is caught."""
    defaults_dir = minimal_valid_config / "defaults"

    with open(defaults_dir / "workflows.yaml", "w") as f:
        yaml.dump(
            {
                "workflows": [
                    {
                        "name": "existing_workflow",
                        "description": "Test",
                        "steps": [
                            {
                                "name": "step1",
                                "component": "comp1",
                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
                                "depends_on": [],
                                "timeout_seconds": 60,
                            }
                        ],
                    }
                ]
            },
            f,
        )

    with open(defaults_dir / "domains.yaml", "w") as f:
        yaml.dump(
            {"domains": [{"name": "default", "workflow": "nonexistent_workflow"}]},  # Wrong name!
            f,
        )

    loader = YamlFileConfigLoader(config_dir=minimal_valid_config)

    with pytest.raises(ValidationError, match="references non-existent workflow"):
        loader.load()
