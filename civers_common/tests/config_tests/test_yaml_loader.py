"""Tests for BaseYamlConfigLoader."""

from pathlib import Path

import pytest
import yaml

from civers_common.configs.exceptions import ConfigurationError
from civers_common.configs.loaders import BaseYamlConfigLoader


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with defaults and environments."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()
    (environments_dir / "testing.yaml").write_text("{}\n")
    return tmp_path


@pytest.fixture()
def _write_yaml(config_dir: Path):
    """Return a writer that drops a YAML file into a subdirectory of the config dir."""

    def _write(subdir: str, filename: str, data: dict) -> Path:
        target_dir = config_dir / subdir
        target_dir.mkdir(exist_ok=True)
        target = target_dir / filename
        target.write_text(yaml.dump(data))
        return target

    return _write


@pytest.mark.parametrize(
    "text",
    [
        "app: {}\napp: {}\n",
        "app:\n  name: one\n  name: two\n",
        "pipeline:\n  fetch:\n    mode: resource_url\n    mode: resource_url\n",
        "app: &a {name: one}\nother: {<<: *a, name: two}\n",
    ],
)
def test_duplicate_keys_are_always_rejected(tmp_path, text):
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Duplicate YAML key"):
        BaseYamlConfigLoader._load_yaml_file(path)


@pytest.mark.parametrize("text", ["[]", "text", "42", "false"])
def test_configuration_document_requires_mapping(tmp_path, text):
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must contain a mapping"):
        BaseYamlConfigLoader._load_yaml_file(path)


@pytest.mark.parametrize("text", ["false: value", "42: value", "? [a, b]\n: value"])
def test_mapping_keys_require_text(tmp_path, text):
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="mapping keys must be text"):
        BaseYamlConfigLoader._load_yaml_file(path)


@pytest.mark.parametrize("content", [b"app: [", b"app: \xff"])
def test_invalid_yaml_and_encoding_fail_safely(tmp_path, content):
    path = tmp_path / "settings.yaml"
    path.write_bytes(content)
    with pytest.raises(ConfigurationError, match="valid UTF-8 YAML"):
        BaseYamlConfigLoader._load_yaml_file(path)


def test_missing_and_empty_documents_return_empty_settings(tmp_path):
    path = tmp_path / "settings.yaml"
    assert BaseYamlConfigLoader._load_yaml_file(path) == {}
    path.write_text("", encoding="utf-8")
    assert BaseYamlConfigLoader._load_yaml_file(path) == {}


def test_quoted_keys_and_utf8_text_are_preserved(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text('"false": "café"\n"42": "München"\n', encoding="utf-8")
    assert BaseYamlConfigLoader._load_yaml_file(path) == {"false": "café", "42": "München"}


def test_nonconflicting_merges_and_keys_in_separate_mappings_are_allowed(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "base: &base {name: one}\n"
        "other: {<<: *base, enabled: true}\n"
        "third: {name: two}\n",
        encoding="utf-8",
    )
    assert BaseYamlConfigLoader._load_yaml_file(path) == {
        "base": {"name": "one"},
        "other": {"name": "one", "enabled": True},
        "third": {"name": "two"},
    }


class TestBaseYamlConfigLoader:
    """Test BaseYamlConfigLoader."""

    @pytest.mark.parametrize("relative_path", ["defaults/app.yaml", "environments/testing.yaml"])
    def test_load_rejects_duplicate_keys_in_each_layer(self, config_dir: Path, relative_path):
        (config_dir / relative_path).write_text(
            "app:\n  name: one\n  name: two\n", encoding="utf-8"
        )
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        with pytest.raises(ConfigurationError, match="Duplicate YAML key"):
            loader.load_raw()

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
        
    def test_empty_mapping_override_does_not_clear_defaults(
        self, config_dir: Path, _write_yaml
    ):
        """Two dicts always merge, so an empty mapping is a no-op, not a reset."""
        _write_yaml("defaults", "kafka.yaml", {"transport": {"enabled": ["kafka"]}})
        _write_yaml("environments", "testing.yaml", {"transport": {}})
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["transport"] == {"enabled": ["kafka"]}

    def test_blank_key_mapping_override_does_not_clear_defaults(self, config_dir: Path):
        """`transport: {""}` is a mapping holding one blank key, so it merges too.

        Written as raw YAML on purpose: the Python literal ``{""}`` is a *set*, which is
        not a dict and so replaces wholesale — the opposite of what the file does.
        """
        (config_dir / "defaults" / "kafka.yaml").write_text(
            "transport:\n  enabled:\n    - kafka\n"
        )
        (config_dir / "environments" / "testing.yaml").write_text('transport: {""}\n')
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["transport"]["enabled"] == ["kafka"]
        assert raw["transport"][""] is None

    def test_list_override_replaces_wholesale(self, config_dir: Path, _write_yaml):
        """Lists are replaced, not concatenated, and sibling keys are left alone.

        Whether the replacement then passes model validation is a separate question the
        loader has no opinion on.
        """
        _write_yaml(
            "defaults",
            "app.yaml",
            {"app": {"tags": ["a", "b"], "name": "default_name"}},
        )
        _write_yaml("environments", "testing.yaml", {"app": {"tags": ["c"]}})
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")
        raw = loader.load_raw()
        assert raw["app"]["tags"] == ["c"]
        assert raw["app"]["name"] == "default_name"

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

    def test_a_required_env_var_that_is_unset_fails_the_load(
        self, config_dir: Path, _write_yaml, monkeypatch
    ):
        """``${VAR}`` with no default is a value the deployment must supply.

        Passing the literal token on would let the service start and fail somewhere far
        away — connecting to a broker named ``${KAFKA_BOOTSTRAP_SERVERS}`` — instead of
        naming the variable that is missing.
        """
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "${MISSING_VAR}"},
        })
        monkeypatch.delenv("MISSING_VAR", raising=False)
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")

        with pytest.raises(ConfigurationError, match="MISSING_VAR"):
            loader.load_raw()

    def test_the_error_names_every_missing_variable_and_where_it_is(
        self, config_dir: Path, _write_yaml, monkeypatch
    ):
        """One boot failure listing all of them beats fix-one, restart, find the next."""
        _write_yaml("defaults", "app.yaml", {
            "app": {"name": "${MISSING_A}", "hosts": ["${MISSING_B}"]},
        })
        monkeypatch.delenv("MISSING_A", raising=False)
        monkeypatch.delenv("MISSING_B", raising=False)
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")

        with pytest.raises(ConfigurationError) as exc_info:
            loader.load_raw()

        message = str(exc_info.value)
        assert "MISSING_A (at app.name)" in message
        assert "MISSING_B (at app.hosts[0])" in message

    def test_a_required_env_var_that_is_set_loads(
        self, config_dir: Path, _write_yaml, monkeypatch
    ):
        _write_yaml("defaults", "app.yaml", {"app": {"name": "${REQUIRED_VAR}"}})
        monkeypatch.setenv("REQUIRED_VAR", "supplied")
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="testing")

        assert loader.load_raw()["app"]["name"] == "supplied"

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

    def test_missing_environment_argument_raises_without_env_variable(self, config_dir, monkeypatch):
        monkeypatch.delenv("CONFIG_ENVIRONMENT", raising=False)
        loader = BaseYamlConfigLoader(config_dir=config_dir, environment="typo")
        with pytest.raises(FileNotFoundError, match="typo"):
            loader.load_raw()

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


class TestEnvVarDefaultsOnEmpty:
    """``:-`` means unset OR empty in every shell, and Docker Compose passes an unset
    host variable through to the container as the empty string."""

    @pytest.mark.parametrize(
        "env,expected",
        [
            ({"CIVERS_PROBE": "set"}, "set"),
            ({"CIVERS_PROBE": ""}, "fallback"),
            ({}, "fallback"),
        ],
    )
    def test_default_applies_when_unset_or_empty(self, monkeypatch, env, expected):
        monkeypatch.delenv("CIVERS_PROBE", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        out = BaseYamlConfigLoader._expand_env_vars({"a": "${CIVERS_PROBE:-fallback}"})

        assert out == {"a": expected}

    def test_a_bare_placeholder_keeps_an_empty_value(self, monkeypatch):
        """``${VAR}`` has no default to fall back to, so "" is the operator's answer."""
        monkeypatch.setenv("CIVERS_PROBE", "")
        assert BaseYamlConfigLoader._expand_env_vars({"a": "${CIVERS_PROBE}"}) == {"a": ""}

    def test_a_bare_placeholder_is_left_intact_when_unset(self, monkeypatch):
        """Left visible in the error rather than silently blank."""
        monkeypatch.delenv("CIVERS_PROBE", raising=False)
        out = BaseYamlConfigLoader._expand_env_vars({"a": "${CIVERS_PROBE}"})
        assert out == {"a": "${CIVERS_PROBE}"}
