"""
Extractor Factory

This module implements the factory pattern for creating appropriate extractors
based on domain configuration and content analysis.

The factory:
1. Analyzes HTML content to determine available extraction methods
2. Matches domain configuration to appropriate extractors
3. Creates and configures extractor instances
4. Provides a unified interface for the extraction system

Mappers are now injected directly into services via dependency injection.

This decouples the extraction service from specific extractor implementations
and makes the system easily extensible.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging

from .base_extractor import BaseExtractor, ExtractionResult
from .html_parser import HTMLParser

logger = logging.getLogger(__name__)


class ExtractorFactory:
    """
    Factory class for creating appropriate extractors.
    
    This factory implements the factory pattern to create extractor instances
    based on domain configuration and content analysis. Mappers are now injected
    directly into services via dependency injection.
    """
    
    def __init__(self):
        """Initialize the factory with empty extractor registry."""
        self._extractors = {}  # extractor_type -> extractor_class
        self._registered = False
        
    def register_extractor(self, extractor_type: str, extractor_class: type) -> None:
        """
        Register an extractor type with the factory.
        
        Args:
            extractor_type: String identifier for the extractor
            extractor_class: Class that implements BaseExtractor
        """
        if not issubclass(extractor_class, BaseExtractor):
            raise ValueError(f"Extractor class must inherit from BaseExtractor")
        
        self._extractors[extractor_type] = extractor_class
        logger.debug(f"Registered extractor: {extractor_type} -> {extractor_class.__name__}")
    
    
    def register_defaults(self) -> None:
        """
        Register default extractors.
        
        This method is called automatically to register the built-in
        extractor implementations. Uses conditional imports to handle
        missing implementations gracefully.
        """
        if self._registered:
            return
            
        registered_extractors = []
        
        # Register extractors with individual try/catch for graceful handling
        try:
            from .extractors.jsonld_extractor import JsonLDExtractor
            self.register_extractor('jsonld', JsonLDExtractor)
            registered_extractors.append('jsonld')
        except ImportError as e:
            logger.warning(f"Could not register JsonLDExtractor: {e}")
        
        try:
            from .extractors.meta_tags_extractor import MetaTagsExtractor
            self.register_extractor('meta_tags', MetaTagsExtractor)
            registered_extractors.append('meta_tags')
        except ImportError as e:
            logger.debug(f"MetaTagsExtractor not available: {e}")
        
        try:
            from .extractors.css_selector_extractor import CSSSelectorsExtractor
            self.register_extractor('css_selectors', CSSSelectorsExtractor)
            registered_extractors.append('css_selectors')
        except ImportError as e:
            logger.debug(f"CSSSelectorsExtractor not available: {e}")
        
        self._registered = True
        logger.info(f"Factory registration completed - Extractors: {registered_extractors}, Mapper: FlattenedToIntermediateModelMapper")
        
        if not registered_extractors:
            logger.warning("No extractors could be registered. System may have limited functionality.")
    
    def analyze_content(self, html_content: str) -> Dict[str, bool]:
        """
        Analyze HTML content to determine available extraction methods.
        
        Currently only supports JSON-LD extraction. Meta tags and CSS selectors
        are placeholder implementations for future development.
        
        Args:
            html_content: HTML content to analyze
            
        Returns:
            Dictionary mapping extraction types to availability
        """
        try:
            soup = HTMLParser.parse_html(html_content)
            
            analysis = {
                'jsonld': False,
                'meta_tags': False,  # Not implemented - placeholder
                'css_selectors': False  # Not implemented - placeholder
            }
            
            # Check for JSON-LD scripts (only implemented extractor)
            jsonld_scripts = HTMLParser.extract_jsonld_scripts(soup)
            analysis['jsonld'] = len(jsonld_scripts) > 0
            
            logger.debug(f"Content analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze content: {e}")
            return {'jsonld': False, 'meta_tags': False, 'css_selectors': False}
    
    def get_extractor(
        self, 
        domain_config: Dict[str, Any], 
        html_content: str
    ) -> Optional[BaseExtractor]:
        """
        Get the appropriate extractor for the given domain and content.
        
        Args:
            domain_config: Domain configuration from app_config.yaml
            html_content: HTML content to process
            
        Returns:
            BaseExtractor instance or None if not possible
        """
        # Ensure defaults are registered
        self.register_defaults()
        
        # Get the configured input source (extractor type)
        input_source = domain_config.get('input_source', 'html_document')
        
        # For backward compatibility, try to infer extractor type
        if input_source == 'html_document':
            # Analyze content to see what's available
            content_analysis = self.analyze_content(html_content)
            
            # Choose first available extractor
            for ext_type in ['jsonld', 'meta_tags', 'css_selectors']:
                if content_analysis.get(ext_type, False):
                    extractor_type = ext_type
                    logger.info(f"Selected {extractor_type} extractor based on content analysis")
                    break
            else:
                logger.error("No suitable extraction method available in content")
                return None
        else:
            extractor_type = input_source
        
        # Create extractor
        extractor = self._create_extractor(extractor_type)
        if not extractor:
            logger.error(f"Failed to create extractor for type: {extractor_type}")
            return None
        
        logger.info(f"Created extractor: {extractor.name}")
        return extractor
    
    def _create_extractor(self, extractor_type: str) -> Optional[BaseExtractor]:
        """Create an extractor instance of the specified type."""
        if extractor_type not in self._extractors:
            logger.error(f"Unknown extractor type: {extractor_type}")
            return None
        
        try:
            extractor_class = self._extractors[extractor_type]
            extractor = extractor_class()
            return extractor
        except Exception as e:
            logger.error(f"Failed to create extractor of type '{extractor_type}': {e}")
            return None
    
    def _find_alternatives(self, content_analysis: Dict[str, bool], preferred_type: str) -> List[str]:
        """
        Find alternative extraction types when preferred type is not available.
        
        Args:
            content_analysis: Results of content analysis
            preferred_type: The originally requested type
            
        Returns:
            List of alternative types in order of preference
        """
        # Priority order for alternatives
        priority_order = ['jsonld', 'meta_tags', 'css_selectors']
        
        # Remove the preferred type from alternatives
        alternatives = [t for t in priority_order if t != preferred_type]
        
        # Filter by availability in content
        available_alternatives = [t for t in alternatives if content_analysis.get(t, False)]
        
        logger.debug(f"Available alternatives for '{preferred_type}': {available_alternatives}")
        return available_alternatives
    
    def get_registered_types(self) -> Dict[str, Any]:
        """
        Get list of registered extractor types and mapper info.
        
        Returns:
            Dictionary with 'extractors' list and 'mapper' info
        """
        self.register_defaults()
        
        return {
            'extractors': list(self._extractors.keys()),
            'mapper': 'FlattenedToIntermediateModelMapper (unified)'
        }
    
    def test_extractor_compatibility(self, extractor_type: str, html_content: str) -> bool:
        """
        Test if an extractor type can handle the given content.
        
        Args:
            extractor_type: Type of extractor to test
            html_content: HTML content to test with
            
        Returns:
            True if extractor can handle the content
        """
        extractor = self._create_extractor(extractor_type)
        if not extractor:
            return False
        
        try:
            return extractor.can_extract(html_content)
        except Exception as e:
            logger.error(f"Error testing extractor compatibility: {e}")
            return False


# Global factory instance
factory = ExtractorFactory()
