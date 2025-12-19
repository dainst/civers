"""Configuration module for CiVers Metadata Extractor.

This module provides configuration loading and validation capabilities:
- YamlFileConfigLoader: Hierarchical config loading with environment support
- ConfigDataModel: Pydantic models for configuration validation
- ConfigValidator: Validation utilities
"""

from abc import ABC, abstractmethod
from .config_data_model import ConfigDataModel
from .config_validator import validate_configuration_file, ConfigValidationError, ConfigValidator
from .loaders import YamlFileConfigLoader

# Legacy config loader interface (deprecated - use YamlFileConfigLoader instead)
class ConfigLoaderInterface(ABC):
    """
    Abstract base class for config loaders.
    
    DEPRECATED: Use YamlFileConfigLoader directly instead.
    """
    @abstractmethod
    def load(self) -> ConfigDataModel:
        """Load configuration and return as ConfigData"""
        pass

# Convenience function for quick configuration validation (legacy)
def validate_config(file_path: str, strict_mode: bool = False) -> ConfigDataModel:
    """
    Convenient wrapper for configuration validation.
    
    DEPRECATED: Use YamlFileConfigLoader().load() for hierarchical config loading.
    
    Args:
        file_path: Path to configuration file
        strict_mode: If True, treats warnings as errors
        
    Returns:
        Validated configuration model
        
    Raises:
        ConfigValidationError: If validation fails
    """
    return validate_configuration_file(file_path, strict_mode=strict_mode)

__all__ = [
    # Primary loader (recommended)
    'YamlFileConfigLoader',
    
    # Data model
    'ConfigDataModel', 
    
    # Validation utilities
    'validate_config',
    'validate_configuration_file',
    'ConfigValidationError',
    'ConfigValidator',
    
    # Legacy interface (deprecated)
    'ConfigLoaderInterface',
]