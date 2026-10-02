"""Shared hierarchical YAML configuration loader for every CiVers service."""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# A ``${VAR}`` placeholder (no ``:-default``) that survived expansion, i.e. a variable
# the deployment was required to set and did not.
_UNRESOLVED_RE = re.compile(r"\$\{([^}:]+)\}")


class _UniqueKeyLoader(yaml.SafeLoader):
    """Require text keys and reject duplicates, including YAML merge collisions."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ConfigurationError("Configuration mapping keys must be text")
            if key in keys:
                raise ConfigurationError("Duplicate YAML key in a configuration document")
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


class BaseYamlConfigLoader:
    """Load and merge CiVers configuration from YAML files.

    Merges ``defaults/*.yaml`` alphabetically, applies ``environments/<env>.yaml`` over
    them, then expands ``${VAR:-default}`` placeholders from the environment.

    The environment is ``CONFIG_ENVIRONMENT`` if set, else "docker" when /.dockerenv
    exists, else "testing" under pytest, else "development".
    """

    def __init__(
        self,
        config_dir: Path | None = None,
        environment: str | None = None,
    ) -> None:
        if config_dir is None:
            if env_config_dir := os.getenv("CONFIG_DIR"):
                config_dir = Path(env_config_dir)
            else:
                # Subclasses can override _default_config_dir
                config_dir = self._default_config_dir()

        self.config_dir = config_dir
        self.defaults_dir = config_dir / "defaults"
        self.environments_dir = config_dir / "environments"
        self.environment = environment or self._detect_environment()
        self._explicit_environment = environment is not None or os.getenv("CONFIG_ENVIRONMENT") is not None

    def _default_config_dir(self) -> Path:
        """Override in subclasses to set the service-specific default."""
        return Path(__file__).resolve().parent / "data"

    @staticmethod
    def _detect_environment() -> str:
        if env := os.getenv("CONFIG_ENVIRONMENT"):
            return env
        if os.path.exists("/.dockerenv"):
            return "docker"
        if os.getenv("PYTEST_CURRENT_TEST"):
            return "testing"
        return "development"

    @staticmethod
    def _load_yaml_file(path: Path) -> dict[str, Any]:
        """Read a UTF-8 YAML mapping with unique text keys, or empty settings."""
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506
        except (yaml.YAMLError, UnicodeError):
            raise ConfigurationError("Configuration must contain valid UTF-8 YAML") from None
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ConfigurationError("A configuration document must contain a mapping")
        return data

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = BaseYamlConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_defaults(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self.defaults_dir.exists():
            for yaml_file in sorted(self.defaults_dir.glob("*.yaml")):
                config = self._deep_merge(config, self._load_yaml_file(yaml_file))
                logger.debug(f"Loaded default config: {yaml_file.name}")
        return config

    def _load_environment_overrides(self) -> dict[str, Any]:
        env_file = self.environments_dir / f"{self.environment}.yaml"
        explicitly_set = self._explicit_environment
        if not env_file.exists():
            if explicitly_set:
                available = (
                    [f.stem for f in self.environments_dir.glob("*.yaml")]
                    if self.environments_dir.exists()
                    else []
                )
                raise FileNotFoundError(
                    f"Environment file '{env_file}' not found. "
                    f"Available: {', '.join(available) or 'none'}"
                )
            logger.warning(
                f"Environment file '{env_file}' not found; using defaults only."
            )
            return {}
        return self._load_yaml_file(env_file)

    @staticmethod
    def _expand_env_vars(config: dict[str, Any]) -> dict[str, Any]:
        """Expand ``${VAR}`` and ``${VAR:-default}`` placeholders from the environment.

        Two limits of the pattern, neither a bug today: the name group excludes ``:``, so
        the shell's ``${VAR-default}`` form is not recognized at all, and a default cannot
        itself contain ``}``.
        """
        env_var_pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

        def expand_value(value: str) -> str:
            def replace(m: re.Match) -> str:
                name, default = m.group(1), m.group(2)
                val = os.getenv(name)
                if default is not None:
                    # ``:-`` means unset OR empty, as in every shell. Docker Compose
                    # passes an unset host variable through as "", so treating empty as
                    # "set" is the common path, not an edge case.
                    return val if val else default
                # Plain ``${VAR}``: leave the token intact when unset, so a required
                # value is visible in the error rather than silently blank.
                return val if val is not None else str(m.group(0))
            return env_var_pattern.sub(replace, value)

        def process(v: Any) -> Any:
            if isinstance(v, dict):
                return {k: process(val) for k, val in v.items()}
            if isinstance(v, list):
                return [process(item) for item in v]
            if isinstance(v, str):
                return expand_value(v)
            return v

        return process(config)

    @staticmethod
    def _unresolved_placeholders(config: dict[str, Any]) -> list[str]:
        """Variable names still written as ``${VAR}`` after expansion, in file order."""
        found: list[str] = []

        def walk(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{path}.{key}" if path else str(key))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")
            elif isinstance(value, str):
                for name in _UNRESOLVED_RE.findall(value):
                    found.append(f"{name} (at {path})")

        walk(config, "")
        return found

    def load_raw(self) -> dict[str, Any]:
        """Load, merge, and expand config — returns raw dict.

        Raises:
            ConfigurationError: A ``${VAR}`` placeholder with no default was left
                unresolved. Passing the literal token through would let a service start
                and then fail somewhere far away — connecting to a broker named
                ``${KAFKA_BOOTSTRAP_SERVERS}`` — instead of naming the missing variable.
        """
        logger.info(f"🔧 Loading configuration for environment: {self.environment}")
        config = self._load_defaults()
        env_config = self._load_environment_overrides()
        merged = self._deep_merge(config, env_config)
        expanded = self._expand_env_vars(merged)

        missing = self._unresolved_placeholders(expanded)
        if missing:
            raise ConfigurationError(
                "Required environment variable(s) are not set: "
                + "; ".join(missing)
                + ". Set them, or give the placeholder a default with ${VAR:-value}."
            )
        return expanded
