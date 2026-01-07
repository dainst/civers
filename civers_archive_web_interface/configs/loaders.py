"""
Configuration loader for centralized configuration management.

This module provides functions to load application configuration from
YAML files with hierarchical merging and environment variable expansion.
It follows the standard CiVers configuration pattern while remaining
independent of other components' code.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml
from pydantic import BaseModel

from configs.models import AppConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


class YamlFileConfigLoader:
    """
    Load configuration from YAML files with hierarchical merging.
    
    Supports:
    - Default configurations in 'defaults/' directory
    - Environment-specific overrides in 'environments/' directory
    - Automatic environment detection (CONFIG_ENVIRONMENT, Docker, Pytest)
    - Environment variable expansion (${VAR:-default})
    - Deep merging of configuration dictionaries
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        environment: Optional[str] = None,
    ) -> None:
        """
        Initialize the configuration loader.

        Args:
            config_dir: Directory containing config files (defaults to 'config/data/')
            environment: Environment name (auto-detected if None)
        """
        if config_dir is None:
            # Check for CONFIG_DIR environment variable
            if env_config_dir := os.getenv("CONFIG_DIR"):
                config_dir = Path(env_config_dir)
            else:
                # Default to configs/data/ relative to project root
                # This file is at configs/loaders.py
                current_file = Path(__file__).resolve()
                config_dir = current_file.parent / "data"

        self.config_dir = config_dir
        self.defaults_dir = config_dir / "defaults"
        self.environments_dir = config_dir / "environments"
        self.environment = environment or self._detect_environment()
        
        logger.debug(f"Config loader initialized: dir={self.config_dir}, env={self.environment}")

    def _detect_environment(self) -> str:
        """Auto-detect the runtime environment."""
        if env := os.getenv("CONFIG_ENVIRONMENT"):
            return env
        if os.path.exists("/.dockerenv"):
            return "docker"
        if os.getenv("PYTEST_CURRENT_TEST"):
            return "testing"
        return "development"

    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a single YAML file."""
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Failed to load YAML file {file_path}: {e}")
            return {}

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
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
            # Load domains.yaml first if it exists (allows storage to override domain properties if needed)
            # Actually, standard is alphabetically
            for yaml_file in sorted(self.defaults_dir.glob("*.yaml")):
                file_config = self._load_yaml_file(yaml_file)
                config = self._deep_merge(config, file_config)
        return config

    def _load_environment_overrides(self) -> Dict[str, Any]:
        """Load environment-specific configuration overrides."""
        env_file = self.environments_dir / f"{self.environment}.yaml"
        return self._load_yaml_file(env_file)

    def _expand_env_vars(self, config: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        env_var_pattern = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')

        def expand_value(value: str) -> str:
            def replace_match(match: re.Match) -> str:
                var_name = match.group(1)
                default_value = match.group(2)
                env_value = os.getenv(var_name)
                if env_value is not None:
                    return env_value
                return default_value if default_value is not None else match.group(0)
            return env_var_pattern.sub(replace_match, value)

        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            return expand_value(config)
        return config

    def load(self, model_class: Type[T]) -> T:
        """
        Load, merge, and validate configuration.
        
        Args:
            model_class: Pydantic model class to validate against
            
        Returns:
            Validated configuration model instance
        """
        # 1. Load defaults
        config = self._load_defaults()
        
        # 2. Load environment overrides
        env_config = self._load_environment_overrides()
        
        # 3. Merge
        merged_config = self._deep_merge(config, env_config)
        
        # 4. Expand environment variables
        expanded_config = self._expand_env_vars(merged_config)
        
        # 5. Backward compatibility: also apply old-style CIVERS_ overrides if present
        # This ensures legacy deployments still work without changing their env vars
        expanded_config = _apply_legacy_overrides(expanded_config)        
        # 6. Validate
        try:
            return model_class(**expanded_config)
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Configuration validation failed: {e}") from e


def load_app_config(config_dir: Optional[Path] = None) -> AppConfig:
    """
    Main entry point for loading application configuration.
    
    Args:
        config_dir: Directory containing config files (default: config/data/)
        
    Returns:
        AppConfig instance
    """
    loader = YamlFileConfigLoader(config_dir=config_dir)
    return loader.load(AppConfig)


def _apply_legacy_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply old-style CIVERS_ environment variable overrides for backward compatibility.
    
    This matches the logic from the previous loader implementation.
    """
    if 'storage' not in config: config['storage'] = {}
    
    # Storage type
    if val := os.getenv('CIVERS_STORAGE_TYPE'):
        config['storage']['type'] = val
        
    # Filesystem
    if val := os.getenv('CIVERS_FILESYSTEM_PATH'):
        if 'filesystem' not in config['storage']: config['storage']['filesystem'] = {}
        config['storage']['filesystem']['path'] = val
        
    if val := os.getenv('CIVERS_FILESYSTEM_TIMEOUT_SECONDS'):
        if 'filesystem' not in config['storage']: config['storage']['filesystem'] = {}
        config['storage']['filesystem']['timeout_seconds'] = int(val)
        
    # Cache
    if val := os.getenv('CIVERS_CACHE_TTL_SECONDS'):
        if 'cache' not in config['storage']: config['storage']['cache'] = {}
        config['storage']['cache']['ttl_seconds'] = int(val)
        
    # Validation
    if 'validation' not in config: config['validation'] = {}
    v_map = {
        'CIVERS_VALIDATION_SNAPSHOT_ID_PATTERN': 'snapshot_id_pattern',
        'CIVERS_VALIDATION_SNAPSHOT_ID_MAX_LENGTH': 'snapshot_id_max_length',
        'CIVERS_VALIDATION_SNAPSHOT_DIRECTORY_PREFIX': 'snapshot_directory_prefix',
        'CIVERS_VALIDATION_FILENAME_MAX_LENGTH': 'filename_max_length',
    }
    for env, key in v_map.items():
        if val := os.getenv(env):
            # Try to convert to int if possible
            try: config['validation'][key] = int(val)
            except ValueError: config['validation'][key] = val
            
    # Kafka
    if 'kafka' not in config: config['kafka'] = {}
    if val := (os.getenv('KAFKA_BOOTSTRAP_SERVERS') or os.getenv('CIVERS_KAFKA_BOOTSTRAP_SERVERS')):
        config['kafka']['bootstrap_servers'] = val
    if val := os.getenv('CIVERS_KAFKA_ENABLED'):
        config['kafka']['enabled'] = val.lower() in ('true', '1', 'yes')
        
    return config