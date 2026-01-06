"""
Configuration loader for centralized configuration management.

This module provides functions to load application configuration from
YAML files with environment variable overrides.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .models import AppConfig

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


def load_app_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Load application configuration from YAML file with environment variable overrides.
    
    Args:
        config_path: Path to configuration file (default: config/storage.yaml)
        
    Returns:
        AppConfig instance with validated configuration
        
    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    try:
        # Use default config path if not specified
        if config_path is None:
            config_path = Path("config/storage.yaml")
        
        # Load YAML configuration
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        if not config_dict:
            raise ConfigurationError("Configuration file is empty")
        
        # Apply environment variable overrides
        config_dict = _apply_environment_overrides(config_dict)
        
        # Create and validate configuration
        app_config = AppConfig(**config_dict)
        
        logger.debug("Application configuration loaded successfully")
        return app_config
        
    except yaml.YAMLError as e:
        raise ConfigurationError(f"YAML parsing error: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Configuration loading failed: {e}") from e


def _apply_environment_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Environment variables follow the pattern: CIVERS_<SECTION>_<KEY>
    
    Args:
        config: Base configuration dictionary
        
    Returns:
        Configuration with environment overrides applied
    """
    # Ensure storage section exists
    if 'storage' not in config:
        config['storage'] = {}
    
    # Storage type override
    storage_type = os.getenv('CIVERS_STORAGE_TYPE')
    if storage_type:
        config['storage']['type'] = storage_type
        logger.debug(f"Storage type overridden by environment: {storage_type}")
    
    # Filesystem overrides
    fs_path = os.getenv('CIVERS_FILESYSTEM_PATH')
    if fs_path:
        if 'filesystem' not in config['storage']:
            config['storage']['filesystem'] = {}
        config['storage']['filesystem']['path'] = fs_path
        logger.debug(f"Filesystem path overridden by environment: {fs_path}")
    
    fs_timeout = os.getenv('CIVERS_FILESYSTEM_TIMEOUT_SECONDS')
    if fs_timeout:
        if 'filesystem' not in config['storage']:
            config['storage']['filesystem'] = {}
        config['storage']['filesystem']['timeout_seconds'] = int(fs_timeout)
        logger.debug(f"Filesystem timeout overridden by environment: {fs_timeout}")
    
    # Cache overrides
    cache_ttl = os.getenv('CIVERS_CACHE_TTL_SECONDS')
    if cache_ttl:
        if 'cache' not in config['storage']:
            config['storage']['cache'] = {}
        config['storage']['cache']['ttl_seconds'] = int(cache_ttl)
        logger.debug(f"Cache TTL overridden by environment: {cache_ttl}")
    
    # Validation overrides
    validation_overrides = {
        'CIVERS_VALIDATION_SNAPSHOT_ID_PATTERN': ('snapshot_id_pattern', str),
        'CIVERS_VALIDATION_SNAPSHOT_ID_MAX_LENGTH': ('snapshot_id_max_length', int),
        'CIVERS_VALIDATION_SNAPSHOT_DIRECTORY_PREFIX': ('snapshot_directory_prefix', str),
        'CIVERS_VALIDATION_FILENAME_MAX_LENGTH': ('filename_max_length', int),
    }
    
    for env_var, (config_key, value_type) in validation_overrides.items():
        env_value = os.getenv(env_var)
        if env_value:
            if 'validation' not in config:
                config['validation'] = {}
            config['validation'][config_key] = value_type(env_value)
            logger.debug(f"Validation {config_key} overridden by environment: {env_value}")
    
    # Kafka overrides
    # Check for KAFKA_BOOTSTRAP_SERVERS (standard Kafka env var) or CIVERS_KAFKA_BOOTSTRAP_SERVERS
    kafka_bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS') or os.getenv('CIVERS_KAFKA_BOOTSTRAP_SERVERS')
    if kafka_bootstrap:
        if 'kafka' not in config:
            config['kafka'] = {}
        config['kafka']['bootstrap_servers'] = kafka_bootstrap
        logger.debug(f"Kafka bootstrap servers overridden by environment: {kafka_bootstrap}")
    
    # Kafka enabled override
    kafka_enabled = os.getenv('CIVERS_KAFKA_ENABLED')
    if kafka_enabled is not None:
        if 'kafka' not in config:
            config['kafka'] = {}
        config['kafka']['enabled'] = kafka_enabled.lower() in ('true', '1', 'yes')
        logger.debug(f"Kafka enabled overridden by environment: {kafka_enabled}")
    
    return config