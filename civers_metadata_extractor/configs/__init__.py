"""Configuration module for CiVers Metadata Extractor.

Provides hierarchical configuration loading and Pydantic validation:
- YamlFileConfigLoader: hierarchical config loading with environment support
  (subclass of ``civers_common.BaseYamlConfigLoader``)
- ConfigDataModel: Pydantic models for configuration validation, with shared
  domain resolution from ``civers_common.DomainResolutionMixin``
"""

from .loaders import YamlFileConfigLoader
from .models import ConfigDataModel

__all__ = [
    "YamlFileConfigLoader",
    "ConfigDataModel",
]
