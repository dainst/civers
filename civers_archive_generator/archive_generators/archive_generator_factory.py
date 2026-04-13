import logging
from typing import Dict, Type, List, Any

from configs.models import ConfigDataModel, DomainConfig
from archive_generators import ArchiveGeneratorStrategyInterface
from archive_generators.scoop import ScoopGenerator
from archive_generators.singlefile import SingleFileGenerator

logger = logging.getLogger(__name__)

class ArchiveGeneratorFactory:
    """
    Factory for creating and validating archive generators.
    
    This factory manages a registry of available generators and provides 
    methods to instantiate them based on domain configuration.
    """
    
    def __init__(self, config: ConfigDataModel):
        self.config = config
        
        # Registry of available generator classes
        self._generator_classes: Dict[str, Type[ArchiveGeneratorStrategyInterface]] = {
            'scoop': ScoopGenerator,
            'singlefile': SingleFileGenerator,
        }
        
        # Cache for instantiated generators
        self._generator_instances: Dict[str, ArchiveGeneratorStrategyInterface] = {}
        
        logger.debug(f"🏭 Archive generator factory initialized with {len(self._generator_classes)} generator types")

    def validate_domain_configs(self):
        """
        Validate all domain configurations against generator capabilities at startup.
        
        Raises:
            ValueError: If a domain requests an artifact its generator cannot produce.
        """
        for domain in self.config.domains:
            for gen_config in domain.generators:
                gen_name = gen_config.name
                gen_class = self._generator_classes.get(gen_name)
                
                if not gen_class:
                    raise ValueError(f"Domain '{domain.name}' requests unknown generator: {gen_name}")
                
                # Check if all requested artifacts are within generator capabilities
                unsupported = set(gen_config.artifacts) - set(gen_class.CAPABILITIES)
                if unsupported:
                    raise ValueError(
                        f"Domain '{domain.name}' requests unsupported artifacts from generator '{gen_name}': "
                        f"{list(unsupported)}. Supported: {gen_class.CAPABILITIES}"
                    )
        
        logger.info("✅ All domain generator configurations validated successfully")

    def create_generators(self, domain_config: DomainConfig) -> List[ArchiveGeneratorStrategyInterface]:
        """
        Create all required generators for a given domain.
        
        Args:
            domain_config: The configuration for the domain to archive.
            
        Returns:
            List of archive generator strategy instances.
        """
        generators = []
        for gen_config in domain_config.generators:
            generator = self._get_or_create_generator(gen_config.name)
            generators.append(generator)
            
        return generators

    def _get_or_create_generator(self, name: str) -> ArchiveGeneratorStrategyInterface:
        """Helper to reuse generator instances (singleton per factory)."""
        if name not in self._generator_instances:
            gen_class = self._generator_classes.get(name)
            if not gen_class:
                raise ValueError(f"Generator '{name}' not found in registry")
            
            self._generator_instances[name] = gen_class(self.config)
            logger.debug(f"🆕 Instantiated generator: {name}")
            
        return self._generator_instances[name]

    def get_factory_info(self) -> Dict[str, Any]:
        """Get info about supported generators and their capabilities."""
        return {
            'factory_type': 'ArchiveGeneratorFactory',
            'supported_generators': list(self._generator_classes.keys()),
            'capabilities': {
                name: cls.CAPABILITIES for name, cls in self._generator_classes.items()
            }
        }
