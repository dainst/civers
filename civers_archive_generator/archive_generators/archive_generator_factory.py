# archive_generators/archive_generator_factory.py
import logging
from typing import Dict, Type

from configs.models import ConfigDataModel, DomainConfig
from archive_generators import ArchiveGeneratorStrategyInterface
from archive_generators.scoop_archive_generator_strategy import ScoopArchiveGeneratorStrategy

logger = logging.getLogger(__name__)


class ArchiveGeneratorFactory:
    """
    Concrete implementation of archive generator factory.
    
    This factory creates appropriate archive generator instances based on:
    1. Domain configuration requirements (webpage_types, artifacts needed)
    2. Available generator implementations
    3. Configuration settings
    
    Currently supports:
    - Scoop (Node.js) generator for both dynamic and static content
    - Future: SimpleFile generator for static content only
    - Future: Custom generators for specific domains
    """
    
    def __init__(self, config: ConfigDataModel):
        """
        Initialize the factory with configuration.
        
        Args:
            config: Application configuration containing generator settings
        """
        self.config = config
        
        # Registry of available generator types
        self._generator_types: Dict[str, Type[ArchiveGeneratorStrategyInterface]] = {
            'scoop': ScoopArchiveGeneratorStrategy,
            'dynamic': ScoopArchiveGeneratorStrategy,  # Alias for dynamic content
            'static': ScoopArchiveGeneratorStrategy,   # Alias for static content
            # Future generators can be added here:
            # 'simplefile': SimpleFileArchiveGeneratorStrategy,
            # 'custom': CustomArchiveGeneratorStrategy,
        }
        
        logger.debug(f"🏭 Archive generator factory initialized with {len(self._generator_types)} generator types")
    
    def create_generator(self, domain_config: DomainConfig) -> ArchiveGeneratorStrategyInterface:
        """
        Create an archive generator based on domain configuration.
        
        The generator selection logic:
        1. Check if domain has a specific generator type configured
        2. Fall back to webpage_types (dynamic/static)
        3. Use default Scoop generator as last resort
        
        Args:
            domain_config: Domain configuration containing generator requirements
            
        Returns:
            Archive generator instance appropriate for the domain
            
        Raises:
            ValueError: If no suitable generator can be created for the domain
            NotImplementedError: If the required generator type is not implemented
        """
        try:
            # Determine generator type from domain configuration
            generator_type = self._determine_generator_type(domain_config)
            
            logger.debug(f"🎯 Selected generator type '{generator_type}' for domain '{domain_config.name}'")
            
            # Get generator class
            generator_class = self._generator_types.get(generator_type)
            if not generator_class:
                raise NotImplementedError(
                    f"Generator type '{generator_type}' is not implemented. "
                    f"Available types: {list(self._generator_types.keys())}"
                )
            
            # Create and return generator instance
            generator = generator_class(self.config)
            
            logger.info(f"✅ Created {generator_class.__name__} for domain '{domain_config.name}'")
            return generator
            
        except Exception as e:
            logger.error(f"❌ Failed to create generator for domain '{domain_config.name}': {e}")
            raise ValueError(f"Cannot create generator for domain '{domain_config.name}': {e}")
    
    def _determine_generator_type(self, domain_config: DomainConfig) -> str:
        """
        Determine the appropriate generator type for a domain configuration.
        
        Priority order:
        1. Explicit generator_type field in domain config (future feature)
        2. webpage_types field (dynamic/static)
        3. Default to 'scoop'
        
        Args:
            domain_config: Domain configuration
            
        Returns:
            Generator type string
        """
        # Future: Check for explicit generator type in domain config
        # if hasattr(domain_config, 'generator_type') and domain_config.generator_type:
        #     return domain_config.generator_type
        
        # Use webpage_types as generator type indicator
        if hasattr(domain_config, 'webpage_types') and domain_config.webpage_types:
            webpage_type = domain_config.webpage_types.lower()
            
            # Map webpage types to generator types
            if webpage_type in ['dynamic', 'static']:
                return webpage_type
        
        # Default to scoop generator
        logger.debug(f"🎯 Using default 'scoop' generator for domain '{domain_config.name}'")
        return 'scoop'
    
    def get_factory_info(self) -> Dict[str, any]:
        """
        Get information about the factory and its capabilities.
        
        Returns:
            Dict containing factory information and supported generators
        """
        return {
            'factory_type': 'ArchiveGeneratorFactory',
            'supported_generator_types': list(self._generator_types.keys()),
            'total_generators': len(self._generator_types),
            'default_generator': 'scoop',
            'generator_classes': {
                gen_type: gen_class.__name__ 
                for gen_type, gen_class in self._generator_types.items()
            }
        }
