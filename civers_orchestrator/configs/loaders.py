"""Configuration loader for CiVers Orchestrator."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from configs.models import ConfigDataModel
from configs.logging_config import get_logger

logger = get_logger(__name__)


class YamlFileConfigLoader:
    """
    Load configuration from YAML files with hierarchical merging.

    Supports environment-based configuration with automatic detection:
    - CONFIG_ENVIRONMENT environment variable
    - Docker container detection
    - Pytest detection
    - Defaults to 'development'
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        environment: Optional[str] = None,
    ) -> None:
        """
        Initialize the configuration loader.

        Args:
            config_dir: Directory containing config files. Defaults to configs/data/
            environment: Environment name. If None, auto-detected.
        """
        if config_dir is None:
            # Check for CONFIG_DIR environment variable
            if env_config_dir := os.getenv("CONFIG_DIR"):
                config_dir = Path(env_config_dir)
            else:
                # Default to configs/data/ relative to this file
                current_file = Path(__file__).resolve()
                config_dir = current_file.parent / "data"

        self.defaults_dir = config_dir / "defaults"
        self.environments_dir = config_dir / "environments"
        self.environment = environment or self._detect_environment()

    def _detect_environment(self) -> str:
        """
        Auto-detect the runtime environment.

        Priority:
        1. CONFIG_ENVIRONMENT environment variable
        2. Docker detection (/.dockerenv file)
        3. Pytest detection (PYTEST_CURRENT_TEST env var)
        4. Default to 'development'

        Returns:
            Environment name (development, testing, docker, production)
        """
        # Check environment variable
        if env := os.getenv("CONFIG_ENVIRONMENT"):
            return env

        # Check if running in Docker
        if os.path.exists("/.dockerenv"):
            return "docker"

        # Check if running in pytest
        if os.getenv("PYTEST_CURRENT_TEST"):
            return "testing"

        # Default to development
        return "development"

    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load a single YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Dictionary with configuration data
        """
        if not file_path.exists():
            return {}

        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                return {}
            # Ensure we always return a dict
            if not isinstance(data, dict):
                return {}
            return data

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _load_defaults(self) -> Dict[str, Any]:
        """Load all default configuration files."""
        config: Dict[str, Any] = {}
        if self.defaults_dir.exists():
            for yaml_file in sorted(self.defaults_dir.glob("*.yaml")):
                config = self._deep_merge(config, self._load_yaml_file(yaml_file))
        return config

    def _load_environment_overrides(self) -> Dict[str, Any]:
        """Load environment-specific overrides.

        Raises:
            FileNotFoundError: If CONFIG_ENVIRONMENT was explicitly set but the
                corresponding file does not exist.
        """
        env_file = self.environments_dir / f"{self.environment}.yaml"
        if not env_file.exists():
            if os.getenv("CONFIG_ENVIRONMENT"):
                available = sorted(
                    f.stem for f in self.environments_dir.glob("*.yaml")
                ) if self.environments_dir.exists() else []
                raise FileNotFoundError(
                    f"Environment '{self.environment}' was explicitly set via "
                    f"CONFIG_ENVIRONMENT but no config file was found at {env_file}. "
                    f"Available environments: {', '.join(available)}"
                )
            else:
                logger.warning(
                    f"⚠️ Config file not found for auto-detected environment "
                    f"'{self.environment}' at {env_file}. Using defaults only."
                )
                return {}
        return self._load_yaml_file(env_file)

    def _expand_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expand environment variables in configuration values.

        Supports:
        - ${VAR_NAME} - Simple variable substitution
        - ${VAR_NAME:-default} - Variable with default value if not set
        - Partial substitution: "prefix_${VAR}_suffix"
        - Multiple variables: "${VAR1}:${VAR2}"

        Args:
            config: Configuration dictionary

        Returns:
            Configuration with expanded environment variables
        """
        import re

        # Pattern matches ${VAR} or ${VAR:-default}
        env_var_pattern = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')

        def expand_value(value: str) -> str:
            """Expand all environment variables in a string value."""
            def replace_match(match: re.Match) -> str:
                var_name = match.group(1)
                default_value = match.group(2)  # None if no default specified

                env_value = os.getenv(var_name)
                if env_value is not None:
                    return env_value
                elif default_value is not None:
                    return default_value
                else:
                    # Return original placeholder if no value and no default
                    return match.group(0)

            return env_var_pattern.sub(replace_match, value)

        def process_value(value: Any) -> Any:
            """Recursively process configuration values."""
            if isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            elif isinstance(value, str):
                return expand_value(value)
            else:
                return value

        return process_value(config)

    def load(self) -> ConfigDataModel:
        """
        Load and merge configuration from all sources.

        Process:
        1. Load default configurations
        2. Load environment-specific overrides
        3. Merge configurations (environment overrides defaults)
        4. Expand environment variables
        5. Validate with Pydantic models

        Returns:
            Validated configuration model

        Raises:
            ValidationError: If configuration is invalid
            FileNotFoundError: If required config files are missing
        """
        # Load defaults
        config = self._load_defaults()

        # Load environment overrides
        env_config = self._load_environment_overrides()

        # Merge configurations
        merged_config = self._deep_merge(config, env_config)

        # Expand environment variables
        expanded_config = self._expand_env_vars(merged_config)

        # Validate and return
        return ConfigDataModel(**expanded_config)
