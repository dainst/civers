"""Hierarchical YAML configuration loader for CiVers ChangeDetection.

Thin wrapper over ``civers_common.BaseYamlConfigLoader`` that points at this
service's ``configs/data`` directory and validates the merged config into a
``ConfigDataModel``.
"""

import logging
from pathlib import Path

from civers_common import BaseYamlConfigLoader

from .models import ConfigDataModel

logger = logging.getLogger(__name__)


class YamlFileConfigLoader(BaseYamlConfigLoader):
    """Load and merge CiVers ChangeDetection configuration from YAML files."""

    def _default_config_dir(self) -> Path:
        return Path(__file__).resolve().parent / "data"

    def load(self) -> ConfigDataModel:
        """Load, merge, expand, and validate the configuration."""
        raw = self.load_raw()
        result = ConfigDataModel(**raw)
        logger.info(f"✅ Configuration loaded for environment: {self.environment}")
        return result
