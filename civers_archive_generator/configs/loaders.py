"""Load shared YAML from configs/data/archive_generator/ into ConfigDataModel."""

import logging
from pathlib import Path

from civers_common import BaseYamlConfigLoader

from .models import ConfigDataModel

logger = logging.getLogger(__name__)


class YamlFileConfigLoader(BaseYamlConfigLoader):
    """Load and merge CiVers Archive Generator configuration from YAML files."""

    def _default_config_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "configs" / "data" / "archive_generator"

    def load(self) -> ConfigDataModel:
        """Merge YAML files, expand environment variables and validate the result."""
        raw = self.load_raw()
        result = ConfigDataModel(**raw)
        logger.info(f"✅ Configuration loaded for environment: {self.environment}")
        return result
