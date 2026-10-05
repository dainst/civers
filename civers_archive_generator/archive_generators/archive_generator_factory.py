"""Builds archive generators from a domain's configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Type

from archive_generators import ArchiveGeneratorStrategyInterface
from archive_generators.scoop import ScoopGenerator
from archive_generators.singlefile import SingleFileGenerator
from archive_generators.browsertrix import BrowsertrixGenerator

if TYPE_CHECKING:
    from configs.models import ConfigDataModel, DomainConfig

logger = logging.getLogger(__name__)

class ArchiveGeneratorFactory:
    """Build and reuse one instance of each configured generator."""

    # Register implementations here; each class declares its own CAPABILITIES.
    _generator_classes: ClassVar[Dict[str, Type[ArchiveGeneratorStrategyInterface]]] = {
        'scoop': ScoopGenerator,
        'singlefile': SingleFileGenerator,
        'browsertrix': BrowsertrixGenerator,
    }

    def __init__(self, config: ConfigDataModel):
        self.config = config
        
        self._generator_instances: Dict[str, ArchiveGeneratorStrategyInterface] = {}
        
        logger.debug(f"🏭 Archive generator factory initialized with {len(self._generator_classes)} generator types")

    @classmethod
    def get_generator_class(cls, name: str) -> Type[ArchiveGeneratorStrategyInterface]:
        """Find a registered generator class without creating an instance."""
        generator_class = cls._generator_classes.get(name)
        if generator_class is None:
            raise ValueError(f"Unknown generator: {name}")
        return generator_class

    def validate_domain_configs(self):
        """Check every domain's requested artifacts against its generators' capabilities.

        Raises:
            ValueError: A domain requests an artifact its generator cannot produce.
        """
        for domain in self.config.domains:
            for gen_config in domain.generators:
                gen_name = gen_config.name
                gen_class = self._generator_classes.get(gen_name)
                
                if not gen_class:
                    raise ValueError(f"Domain '{domain.name}' requests unknown generator: {gen_name}")
                
                unsupported = set(gen_config.artifacts) - set(gen_class.CAPABILITIES)
                if unsupported:
                    raise ValueError(
                        f"Domain '{domain.name}' requests unsupported artifacts from generator '{gen_name}': "
                        f"{list(unsupported)}. Supported: {gen_class.CAPABILITIES}"
                    )
        
        logger.info("✅ All domain generator configurations validated successfully")

    def create_generators(self, domain_config: DomainConfig):
        """Return (config, generator) pairs in the configured order.

        Raise ValueError for an unregistered generator name.
        """
        generators = []
        for gen_config in domain_config.generators:
            generator = self._get_or_create_generator(gen_config.name)
            generators.append((gen_config, generator))
            
        return generators

    def _get_or_create_generator(self, name: str) -> ArchiveGeneratorStrategyInterface:
        """Return the named generator, building it once and reusing it thereafter."""
        if name not in self._generator_instances:
            gen_class = self._generator_classes.get(name)
            if not gen_class:
                raise ValueError(f"Generator '{name}' not found in registry")
            
            self._generator_instances[name] = gen_class(self.config)
            logger.debug(f"🆕 Instantiated generator: {name}")
            
        return self._generator_instances[name]

    def get_factory_info(self) -> Dict[str, Any]:
        """Return the registered generator names and what each can produce."""
        return {
            'factory_type': 'ArchiveGeneratorFactory',
            'supported_generators': list(self._generator_classes.keys()),
            'capabilities': {
                name: cls.CAPABILITIES for name, cls in self._generator_classes.items()
            }
        }
