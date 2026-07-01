"""Tests for BaseYamlConfigLoader."""

from pathlib import Path

import pytest
import yaml

from civers_common.configs.loaders import BaseYamlConfigLoader


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with defaults and environments."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()
    return tmp_path


@pytest.fixture()
def _write_yaml(config_dir: Path):
    """Helper to write YAML files into the config directory."""

    def _write(subdir: str, filename: str, data: dict) -> Path:
        target_dir = config_dir / subdir
        target_dir.mkdir(exist_ok=True)
        target = target_dir / filename
        target.write_text(yaml.dump(data))
        return target

    return _write


class TestBaseYamlConfigLoader:
    """Test BaseYamlConfigLoader."""

    def test_load_defaults(self, config_dir: Path, _write_yaml):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "test"}})
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "test"

    def test_load_multiple_defaults_merged(self, config_dir: Path, _write_yaml):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "test"}})
        _write_yaml("defaults", "kafka.yaml", {"transport": {"enabled": ["kafka"]}})
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "test"
        assert raw["transport"]["enabled"] == ["kafka"]

    def test_environment_overrides_defaults(self, config_dir: Path, _write_yaml):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "default_name"}})
        _write_yaml("environments", "testing.yaml", {"app": {"name": "testing_name"}})
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "testing_name"

    def test_deep_merge_preserves_nested(self, config_dir: Path, _write_yaml):
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "test", "version": "1.0"},
        })
        _write_yaml("environments", "testing.yaml", {
            "app": {"name": "overridden"},
        })
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "overridden"
        assert raw["app"]["version"] == "1.0"

    def test_env_var_expansion(self, config_dir: Path, _write_yaml, monkeypatch):
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "${APP_NAME:-fallback}"},
        })
        monkeypatch.setenv("APP_NAME", "from_env")
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "from_env"

    def test_env_var_fallback(self, config_dir: Path, _write_yaml, monkeypatch):
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "${MISSING_VAR:-fallback_value}"},
        })
        monkeypatch.delenv("MISSING_VAR", raising=False)
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "fallback_value"

    def test_env_var_no_fallback_preserved(self, config_dir: Path, _write_yaml, monkeypatch):
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "${MISSING_VAR}"},
        })
        monkeypatch.delenv("MISSING_VAR", raising=False)
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "${MISSING_VAR}"

    def test_missing_env_file_with_explicit_config_raises(
        self, config_dir: Path, _write_yaml, monkeypatch
    ):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "test"}})
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "nonexistent")
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="nonexistent")
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load_raw()

    def test_empty_defaults_dir(self, config_dir: Path):
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw == {}

    def test_config_dir_from_env(self, config_dir: Path, _write_yaml, monkeypatch):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "from_env_dir"}})
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        loader = BaseYamlConfigLoader(environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["name"] == "from_env_dir"


class TestEnvironmentDetection:
    """Test BaseYamlConfigLoader._detect_environment()."""

    def test_config_environment_env_var(self, monkeypatch):
        monkeypatch.setenv("CONFIG_ENVIRONMENT", "staging")
        assert BaseYamlConfigLoader._detect_environment() == "staging"

    def test_pytest_detection(self, monkeypatch):
        monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
        # PYTEST_CURRENT_TEST is set automatically by pytest
        assert BaseYamlConfigLoader._detect_environment() == "testing"

    def test_fallback_development(self, monkeypatch):
        monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        assert BaseYamlConfigLoader._detect_environment() == "development"
