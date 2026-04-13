"""
JSON-LD Metadata Extractors Package

This package contains specialized JSON-LD metadata extraction functionality that handles
structured JSON-LD data and maps it to the intermediate DataCite-based metadata model.

Current Architecture:
- JSON-LD Strategy: Specialized extraction from JSON-LD scripts
- Factory Pattern: Intelligent content analysis and extractor selection
- Mapping Layer: Convert extracted data to standardized DataCite model

Future Development:
- Meta tags extraction (planned)
- CSS selector extraction (planned)

See DEVELOPMENT_ROADMAP.md for implementation timeline.
"""

# Import error handling for incomplete implementation
try:
    from .base_extractor import BaseExtractor, ExtractionResult
    from .extractor_factory import ExtractorFactory
    from .html_parser import HTMLParser

    __all__ = ["BaseExtractor", "ExtractionResult", "ExtractorFactory", "HTMLParser"]
except ImportError as e:
    # During development, some modules might not be complete
    __all__ = []
    import logging

    logging.getLogger(__name__).debug(f"Import error in metadata_extractors: {e}")
