"""
Generic JSON-LD Extractor

This module implements a generic JSON-LD extractor that extracts raw structured data
from JSON-LD script tags in HTML documents. It works with any JSON-LD structure,
not tied to specific Schema.org types or website patterns.

The extractor:
1. Finds all <script type="application/ld+json"> tags
2. Parses the JSON content to Python dictionaries
3. Flattens nested structures with dot notation keys
4. Returns raw data for configuration-driven mapping
"""

import logging
import time
from typing import Any

from ..base_extractor import BaseExtractor, ExtractionResult, ExtractionStatus
from ..html_parser import HTMLParser

logger = logging.getLogger(__name__)


class JsonLDExtractor(BaseExtractor):
    """
    Generic extractor for JSON-LD structured data from HTML script tags.

    This extractor works with any JSON-LD structure, not tied to specific
    Schema.org types or website patterns. It flattens nested JSON-LD objects
    into a flat dictionary with simple dot notation keys for easy mapping.

    Examples:
    {"author": {"name": "John", "@type": "Person"}}
    becomes: {"author.name": "John", "author.@type": "Person"}

    {"authors": [{"name": "John"}, {"name": "Jane"}]}
    becomes: {"authors[0].name": "John", "authors[1].name": "Jane"}
    """


    def extract(self, html_content: str, source_url: str) -> ExtractionResult:
        """
        Extract raw JSON-LD data from HTML content and flatten it.

        Args:
            html_content: The HTML content to extract metadata from
            source_url: The source URL for context and validation

        Returns:
            ExtractionResult containing the flattened JSON-LD data
        """
        start_time = time.time()

        try:
            # Parse HTML and extract JSON-LD scripts
            soup = HTMLParser.parse_html(html_content)
            jsonld_scripts = HTMLParser.extract_jsonld_scripts(soup)


            if not jsonld_scripts:
                return ExtractionResult(
                    status=ExtractionStatus.FAILED,
                    flattened_raw_data={},
                    extraction_type=self.get_extractor_type(),
                    source_url=source_url,
                    processing_time_seconds=time.time() - start_time,
                    error_message="No JSON-LD scripts found in HTML content",
                )

            # Flatten all JSON-LD scripts into a single dictionary
            flattened_data: dict[str, Any] = {}

            for i, script in enumerate(jsonld_scripts):
                script_prefix = f"script_{i}" if len(jsonld_scripts) > 1 else ""
                logger.debug(f"Flattening JSON-LD script {i}: {len(str(script))} chars")
                self._flatten_json_object(script, flattened_data, script_prefix)
                logger.debug(f"Script {i} generated {len(flattened_data)} keys")

            # Add metadata about extraction
            flattened_data["_meta.source_url"] = source_url
            flattened_data["_meta.script_count"] = len(jsonld_scripts)
            flattened_data["_meta.extraction_timestamp"] = time.time()

            result = ExtractionResult(
                status=ExtractionStatus.SUCCESS,
                flattened_raw_data=flattened_data,
                extraction_type=self.get_extractor_type(),
                source_url=source_url,
                processing_time_seconds=time.time() - start_time,
                metadata_count=len([k for k in flattened_data.keys() if not k.startswith("_meta")]),
            )

            logger.info(
                f"Generic JSON-LD extraction completed: {len(jsonld_scripts)} scripts, {result.metadata_count} fields"
            )
            return result

        except Exception as e:
            logger.error(f"JSON-LD extraction failed: {e}")
            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                flattened_raw_data={},
                extraction_type=self.get_extractor_type(),
                source_url=source_url,
                processing_time_seconds=time.time() - start_time,
                error_message=str(e),
            )

    def get_extractor_type(self) -> str:
        """Get the type identifier for this extractor."""
        return "jsonld"


    def _flatten_json_object(self, obj: Any, result: dict[str, Any], prefix: str = "") -> None:
        """
        Recursively flatten a JSON-LD object into dot notation keys.

        This method delegates to specialized handlers for different data types:
        - _flatten_dictionary_field: handles nested dictionaries
        - _flatten_list_field: handles arrays/lists
        - _flatten_primitive_field: handles primitive values

        Args:
            obj: The JSON object to flatten
            result: Dictionary to store flattened results
            prefix: Current key prefix for nested objects
        """
        if isinstance(obj, dict):
            self._flatten_dictionary_field(obj, result, prefix)
        elif isinstance(obj, list):
            self._flatten_list_field(obj, result, prefix)
        else:
            self._flatten_primitive_field(obj, result, prefix)

    def _flatten_dictionary_field(
        self, dictionary: dict[str, Any], result: dict[str, Any], prefix: str = ""
    ) -> None:
        """
        Flatten a dictionary object into simple dot notation keys.

        Uses simple dot notation without type-aware prefixing for predictable,
        debuggable key structure. @type fields are preserved as separate entries.

        Args:
            dictionary: The dictionary to flatten
            result: Dictionary to store flattened results
            prefix: Current key prefix for nested objects
        """
        for key, value in dictionary.items():
            # Create the full key with simple dot notation
            if prefix:
                full_key = f"{prefix}.{key}"
            else:
                # Root level - use key as is
                full_key = key

            logger.debug(f"Processing key: {full_key} (type: {type(value).__name__})")

            # Recursively flatten the value
            self._flatten_json_object(value, result, full_key)

    def _flatten_list_field(
        self, list_obj: list[Any], result: dict[str, Any], prefix: str = ""
    ) -> None:
        """
        Flatten a list/array object into indexed keys.

        Args:
            list_obj: The list to flatten
            result: Dictionary to store flattened results
            prefix: Current key prefix for nested objects
        """
        for i, item in enumerate(list_obj):
            # Use array index in key
            array_key = f"{prefix}[{i}]" if prefix else f"[{i}]"

            # Recursively flatten the item
            self._flatten_json_object(item, result, array_key)

    def _flatten_primitive_field(
        self, value: Any, result: dict[str, Any], prefix: str = ""
    ) -> None:
        """
        Handle primitive values (strings, numbers, booleans, null).

        Args:
            value: The primitive value to store
            result: Dictionary to store flattened results
            prefix: Current key for the value
        """
        # For primitive values at root level (shouldn't happen in normal JSON-LD)
        # we only store if there's a prefix (key)
        if prefix:
            result[prefix] = value
