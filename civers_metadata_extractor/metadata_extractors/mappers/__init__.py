"""
Mappers Package

This package contains the unified mapper that converts raw extracted metadata
to the standardized DataCite-based intermediate metadata model.

The FlattenedToIntermediateModelMapper is source-agnostic and works with
flattened data from any extractor (JSON-LD, meta tags, CSS selectors, etc.).
"""

from .flattened_to_intermediate_mapper import (
    FlattenedToIntermediateModelMapper,
    MappingResult,
    MappingStatus
)
from .transformation_engine import TransformationEngine
from .key_parser import KeyParser
from .model_constructor import ModelConstructor
from .mapping_adapter import parse_mapping_rules, MappingRule

__all__ = [
    # Main mapper
    'FlattenedToIntermediateModelMapper',
    'MappingResult',
    'MappingStatus',
    
    # Mapper components
    'TransformationEngine',
    'KeyParser',
    'ModelConstructor',
    
    # Utilities
    'parse_mapping_rules',
    'MappingRule',
]
