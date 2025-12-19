"""
Flattened to Intermediate Model Mapper

Universal mapper that transforms flattened data to IntermediateMetadata.
This is a concrete class - no base class needed since we only have one mapper.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

from .transformation_engine import TransformationEngine
from .model_constructor import ModelConstructor
from .mapping_adapter import parse_mapping_rules
from models.intermediate_metadata import IntermediateMetadata, Identifier, IdentifierType

logger = logging.getLogger(__name__)


class MappingStatus(str, Enum):
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
    intermediate_metadata: Optional[IntermediateMetadata]
    mapped_fields_count: int
    source_fields_count: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    skipped_fields_count: int = 0  # For compatibility with service analytics
    skipped_fields_details: List[Dict[str, Any]] = field(default_factory=list)
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
    """
    
    def __init__(self):
        """Initialize the mapper"""
        logger.info("Initialized FlattenedToIntermediateModelMapper")
    
    def map_to_intermediate(
        self, 
        raw_data: Dict[str, Any], 
        domain_config: Dict[str, Any], 
        source_url: str
    ) -> MappingResult:
        """
        Transform flattened data to IntermediateMetadata.
        
        Args:
            raw_data: Flattened data dict from any extractor
            domain_config: Domain configuration with mapping rules
            source_url: Source URL for identifier
            
        Returns:
            MappingResult with IntermediateMetadata
        """
        logger.info(f"Mapping {len(raw_data)} flattened fields to IntermediateMetadata")
        
        try:
            # Extract mapping rules from config (dict format from app_config.yaml)
            mapping_dict = self._extract_mapping_config(domain_config)
            
            # Convert dict mappings to MappingRule objects
            mapping_rules = parse_mapping_rules(mapping_dict)
            logger.debug(f"Parsed {len(mapping_rules)} mapping rules")
            
            # Step 1: Transform flattened data → nested dictionaries
            engine = TransformationEngine(mapping_rules)
            nested_data = engine.transform(raw_data)
            logger.debug(f"Transformed to nested structure with {len(nested_data)} top-level keys")
            
            # Step 2: Post-process nested data to ensure required fields
            self._ensure_required_fields(nested_data)
            
            # Step 3: Construct IntermediateMetadata from nested data
            metadata = ModelConstructor.build(IntermediateMetadata, nested_data)
            logger.info("Successfully constructed IntermediateMetadata")
            
            # Step 4: Add source URL as identifier if not present
            if not metadata.identifier:
                metadata.identifier = Identifier(
                    identifier=source_url,
                    identifier_type=IdentifierType.URL
                )
            
            return MappingResult(
                status=MappingStatus.SUCCESS,
                intermediate_metadata=metadata,
                mapped_fields_count=len(nested_data),
                source_fields_count=len(raw_data)
            )
            
        except Exception as e:
            logger.error(f"Mapping failed: {e}", exc_info=True)
            return MappingResult(
                status=MappingStatus.FAILED,
                intermediate_metadata=None,
                mapped_fields_count=0,
                source_fields_count=len(raw_data),
                errors=[str(e)]
            )
    
    def _extract_mapping_config(self, domain_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract mapping configuration from domain config.
        
        Since mapper config has been removed, mappings are now directly on the domain config.
        """
        return domain_config.get('mappings', {})
    
    def _ensure_required_fields(self, nested_data: Dict[str, Any]) -> None:
        """
        Ensure required DataCite fields have values.
        
        Sets sensible defaults for:
        - publication_year: Extract from dates or use current year
        - resource_type: Default to "Dataset" if not specified
        
        Args:
            nested_data: Nested data dict (modified in place)
        """
        from datetime import datetime
        from models.intermediate_metadata import ResourceType, ResourceTypeGeneral
        
        # Handle publication_year
        if 'publication_year' not in nested_data:
            # Try to extract year from dates
            dates = nested_data.get('dates', [])
            if dates and isinstance(dates, list) and len(dates) > 0:
                # Get first date and try to extract year
                first_date = dates[0]
                if isinstance(first_date, dict) and 'date' in first_date:
                    date_str = first_date['date']
                    try:
                        # Try to parse year from date string (e.g., "2019-03-15")
                        if isinstance(date_str, str) and len(date_str) >= 4:
                            year = int(date_str[:4])
                            if 1000 <= year <= 9999:
                                nested_data['publication_year'] = year
                                logger.debug(f"Extracted publication_year {year} from dates")
                    except  (ValueError, TypeError):
                        pass
            
            # If still no year, use current year as fallback
            if 'publication_year' not in nested_data:
                current_year = datetime.now().year
                nested_data['publication_year'] = current_year
                logger.warning(f"No publication year found, using current year: {current_year}")
        
        # Handle resource_type
        if 'resource_type' not in nested_data:
            # Create a default resource_type
            nested_data['resource_type'] = {
                'resource_type_general': ResourceTypeGeneral.DATASET.value,
                'resource_type': 'Dataset'
            }
            logger.warning("No resource_type found, using default: Dataset")

