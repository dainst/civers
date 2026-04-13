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
    MappingStatus,
)
from .key_parser import KeyParser
from .mapping_adapter import MappingRule, parse_mapping_rules
from .model_constructor import ModelConstructor
from .transformation_engine import TransformationEngine

__all__ = [
    # Main mapper
    "FlattenedToIntermediateModelMapper",
    "MappingResult",
    "MappingStatus",
    # Mapper components
    "TransformationEngine",
    "KeyParser",
    "ModelConstructor",
    # Utilities
    "parse_mapping_rules",
    "MappingRule",
]
