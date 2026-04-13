"""
Flattened to Intermediate Model Mapper

Universal mapper that transforms flattened data to IntermediateMetadata.
This is a concrete class - no base class needed since we only have one mapper.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from models.intermediate_metadata import Identifier, IdentifierType, IntermediateMetadata

from .mapping_adapter import parse_mapping_rules
from .model_constructor import ModelConstructor
from .transformation_engine import TransformationEngine

logger = logging.getLogger(__name__)


class MappingStatus(StrEnum):
    """Status of mapping operation"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class MappingResult:
    """
    Result of a metadata mapping operation.

    Provides standardized return type with status, metadata, statistics, and errors.
    """

    status: MappingStatus
    intermediate_metadata: IntermediateMetadata | None
    mapped_fields_count: int
    source_fields_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_fields_count: int = 0  # For compatibility with service analytics
    skipped_fields_details: list[dict[str, Any]] = field(default_factory=list)
    processing_time_seconds: float = 0.0


class FlattenedToIntermediateModelMapper:
    """
    Universal mapper from flattened data to IntermediateMetadata model.

    This is a concrete class (no base class) since we only need one mapper.
    The extractors (JsonLDExtractor, MetaTagsExtractor, etc.) create flattened
    data, and this mapper transforms it to the intermediate model.

    Flow:
      1. Extractors → Flattened data {\"author[0].name\": \"John\", ...}
      2. TransformationEngine → Nested dicts {\"Creator\": [{\"creator_name\": \"John\"}]}
      3. ModelConstructor → IntermediateMetadata (Pydantic model)

    All DataCite required fields (publication_year, resource_type, creators, titles,
    publisher) must be covered by explicit mapping rules in the domain config.
    Missing required fields surface as a FAILED MappingResult with a clear error.
    """

    def __init__(self):
        """Initialize the mapper"""
        logger.info("Initialized FlattenedToIntermediateModelMapper")

    def map_to_intermediate(
        self, raw_data: dict[str, Any], domain_config: dict[str, Any], source_url: str
    ) -> MappingResult:
        """
        Transform flattened data to IntermediateMetadata.

        Args:
            raw_data: Flattened data dict from any extractor
            domain_config: Domain configuration with mapping rules
            source_url: Source URL for identifier

        Returns:
            MappingResult with IntermediateMetadata, or FAILED status with error details
            if required DataCite fields are not covered by the mapping rules.
        """
        logger.info(f"Mapping {len(raw_data)} flattened fields to IntermediateMetadata")

        try:
            mapping_rules = parse_mapping_rules(domain_config.get("mappings", {}))
            logger.debug(f"Parsed {len(mapping_rules)} mapping rules")

            nested_data = TransformationEngine(mapping_rules).transform(raw_data)
            logger.debug(f"Transformed to nested structure with {len(nested_data)} top-level keys")

            metadata = cast(
                IntermediateMetadata, ModelConstructor.build(IntermediateMetadata, nested_data)
            )
            logger.info("Successfully constructed IntermediateMetadata")

            if not metadata.identifier:
                metadata.identifier = Identifier(
                    identifier=source_url, identifier_type=IdentifierType.URL
                )

            return MappingResult(
                status=MappingStatus.SUCCESS,
                intermediate_metadata=metadata,
                mapped_fields_count=len(nested_data),
                source_fields_count=len(raw_data),
            )

        except Exception as e:
            logger.error(f"Mapping failed: {e}", exc_info=True)
            return MappingResult(
                status=MappingStatus.FAILED,
                intermediate_metadata=None,
                mapped_fields_count=0,
                source_fields_count=len(raw_data),
                errors=[str(e)],
            )
