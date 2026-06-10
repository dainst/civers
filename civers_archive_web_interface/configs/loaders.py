"""
Configuration loader subclassing civers_common BaseYamlConfigLoader.
"""

from pathlib import Path
from civers_common import BaseYamlConfigLoader
from configs.models import AppConfig


class YamlFileConfigLoader(BaseYamlConfigLoader):
    """
    Load configuration from YAML files with hierarchical merging.
    """

    def _default_config_dir(self) -> Path:
        """Default to configs/data/ relative to this file."""
        return Path(__file__).resolve().parent / "data"

    def load(self) -> AppConfig:
        """
        Load and merge configuration from all sources.
        """
        raw = self.load_raw()
        return AppConfig(**raw)



