"""Shared hierarchical YAML configuration loader.

All five services currently have near-identical YamlFileConfigLoader
implementations. This consolidates them into one.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class BaseYamlConfigLoader:
    """Load and merge CiVers configuration from YAML files.

    Loading order:
        1. defaults/*.yaml   (base settings, merged alphabetically)
        2. environments/<env>.yaml  (environment-specific overrides)
        3. Expand ${VAR:-default} placeholders from environment variables

    Environment detection:
        1. CONFIG_ENVIRONMENT env var
        2. Docker detection (/.dockerenv)
        3. Pytest detection (PYTEST_CURRENT_TEST)
        4. Fallback: "development"
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
        if not path.exists():
            return {}
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return {}
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
        explicitly_set = os.getenv("CONFIG_ENVIRONMENT") is not None
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
        env_var_pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

        def expand_value(value: str) -> str:
            def replace(m: re.Match) -> str:
                val = os.getenv(m.group(1))
                if val is not None:
                    return val
                if m.group(2) is not None:
                    return str(m.group(2))
                return str(m.group(0))
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

    def load_raw(self) -> dict[str, Any]:
        """Load, merge, and expand config — returns raw dict."""
        logger.info(f"🔧 Loading configuration for environment: {self.environment}")
        config = self._load_defaults()
        env_config = self._load_environment_overrides()
        merged = self._deep_merge(config, env_config)
        return self._expand_env_vars(merged)
