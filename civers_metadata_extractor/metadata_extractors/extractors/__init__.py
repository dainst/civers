"""
Extractors Package

This package contains specific extractor implementations that handle
different types of metadata extraction from HTML content.

Available extractors:
- JsonLDExtractor: Extracts structured data from JSON-LD scripts
- MetaTagsExtractor: Extracts metadata from HTML meta tags  
- CSSSelectorsExtractor: Extracts content using CSS selectors
"""

from .jsonld_extractor import JsonLDExtractor

__all__ = [
    'JsonLDExtractor'
]
