"""Unit tests for environment validation."""

from pathlib import Path

import pytest

from configs.loaders import YamlFileConfigLoader


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create temporary configuration directory structure."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()

    # Create minimal default config
    import yaml

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
                                "depends_on": [],
                                                                "input_schema": "TestRequest",
                                "output_schemas": {"success": "TestCompleted", "failure": "TestFailed"},
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

    # Create one valid environment file
    with open(environments_dir / "development.yaml", "w") as f:
        yaml.dump({"app": {"environment": "development"}}, f)

    return tmp_path


def test_explicitly_set_nonexistent_environment_raises_error(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that explicitly setting non-existent environment raises FileNotFoundError."""
    # Explicitly set non-existent environment
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "nonexistent")

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)

    # Should raise FileNotFoundError with helpful message
    with pytest.raises(
        FileNotFoundError,
        match="Environment 'nonexistent' was explicitly set via CONFIG_ENVIRONMENT",
    ):
        loader.load()


def test_explicitly_set_nonexistent_environment_lists_available(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that error message lists available environments."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "staging")

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)

    with pytest.raises(FileNotFoundError, match="Available environments:.*development"):
        loader.load()


def test_auto_detected_environment_missing_warns_but_loads(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that auto-detected missing environment file warns but still loads defaults."""
    # Unset CONFIG_ENVIRONMENT to allow auto-detection
    monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
    # Unset other detection mechanisms
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    # Create loader with explicit environment that doesn't exist
    # but simulate it was auto-detected by not setting CONFIG_ENVIRONMENT
    loader = YamlFileConfigLoader(config_dir=temp_config_dir, environment="autodetected")

    # Should load successfully with warning
    config = loader.load()

    # Check warning was logged
    assert "not found for auto-detected environment" in caplog.text
    assert "autodetected" in caplog.text

    # Should still load with defaults
    assert config.app.name == "test"


def test_valid_environment_loads_successfully(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that valid environment loads successfully."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "development")

    loader = YamlFileConfigLoader(config_dir=temp_config_dir)
    config = loader.load()

    assert config.app.environment == "development"
