"""
Extractor Factory

Discovers and registers extractors automatically at startup.

Convention: every file matching `*_extractor.py` in `metadata_extractors/extractors/`
is imported; any `BaseExtractor` subclass found is instantiated once and stored in the
registry keyed by its `get_extractor_type()` return value.

The extractor type in the registry must match the `extractor:` field in the domain config.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class ExtractorFactory:
    """
    Factory that holds singleton extractor instances and resolves them by type name.

    Extractors are stateless — each instance carries only `self.name` — so one
    instance per type is sufficient and safe across concurrent requests.
    """

    def __init__(self):
        self._extractors: dict[str, BaseExtractor] = {}
        self._auto_register()

    def _auto_register(self) -> None:
        """Discover and register all extractors in the extractors/ directory."""
        extractors_dir = Path(__file__).parent / "extractors"
        registered = []

        for path in sorted(extractors_dir.glob("*_extractor.py")):
            module_name = f"metadata_extractors.extractors.{path.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"Could not import extractor module {module_name}: {e}")
                continue

            for _, cls in inspect.getmembers(module, inspect.isclass):
                if issubclass(cls, BaseExtractor) and cls is not BaseExtractor:
                    try:
                        instance = cls()
                        self._extractors[instance.get_extractor_type()] = instance
                        registered.append(instance.get_extractor_type())
                    except Exception as e:
                        logger.warning(f"Could not instantiate {cls.__name__}: {e}")

        logger.info(f"Registered extractors: {registered}")

    def register_extractor(self, extractor_type: str, extractor: BaseExtractor) -> None:
        """
        Register an extractor instance manually.

        Args:
            extractor_type: Registry key (must match extractor's get_extractor_type())
            extractor: Extractor instance
        """
        if not isinstance(extractor, BaseExtractor):
            raise ValueError("extractor must be an instance of BaseExtractor")
        self._extractors[extractor_type] = extractor
        logger.debug(f"Registered extractor: {extractor_type} -> {extractor.__class__.__name__}")

    def get_extractor(self, domain_config: dict[str, Any]) -> BaseExtractor | None:
        """
        Return the extractor instance for the given domain config.

        The `extractor` key in domain_config must match a registered extractor type.

        Args:
            domain_config: Domain configuration dict (from DomainConfig.model_dump())

        Returns:
            Extractor instance, or None if type is missing or unknown
        """
        extractor_type = domain_config.get("extractor")
        if not extractor_type:
            logger.error("No extractor specified in domain config")
            return None

        extractor = self._extractors.get(extractor_type)
        if not extractor:
            logger.error(
                f"Unknown extractor type: '{extractor_type}'. "
                f"Registered types: {list(self._extractors.keys())}"
            )
        return extractor

    def get_registered_types(self) -> dict[str, Any]:
        """
        Return registered extractor type names and their class names.

        Returns:
            Dict with 'extractors' list
        """
        return {
            "extractors": {k: v.__class__.__name__ for k, v in self._extractors.items()},
        }


# Global singleton factory — auto-registers at import time
factory = ExtractorFactory()
