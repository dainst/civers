"""
Mapping Configuration Adapter

Simple data class to adapt dict-based mapping rules for TransformationEngine.
"""

from dataclasses import dataclass
from typing import Any

from .key_parser import KeyParser, PathSegment


@dataclass
class MappingRule:
    """
    Lightweight mapping rule dataclass.

    Replaces the need for config_loader.MappingRule by providing
    a minimal structure for TransformationEngine.
    """

    source_pattern: str
    target_pattern: str
    target_segments: list[PathSegment]
    transformations: dict[str, Any]


def parse_mapping_rules(mapping_dict: dict[str, str]) -> list[MappingRule]:
    """
    Convert dict-based mapping rules to MappingRule objects.

    Args:
        mapping_dict: Dictionary from app_config.yaml {source: target}

    Returns:
        List of MappingRule objects

    Example:
        >>> rules_dict = {
        ...     "name": "Title.title",
        ...     "author[*].name": "Creator[*].creator_name|name_type=Organizational"
        ... }
        >>> rules = parse_mapping_rules(rules_dict)
    """
    parser = KeyParser()
    rules = []

    for source, target in mapping_dict.items():
        # Parse target (may have transformations like |key=value)
        target_path, transformations = _parse_target_with_transformations(target)

        # Parse target path into segments
        target_segments = parser.parse(target_path)

        rules.append(
            MappingRule(
                source_pattern=source,
                target_pattern=target_path,
                target_segments=target_segments,
                transformations=transformations,
            )
        )

    return rules


def _parse_target_with_transformations(target: str) -> tuple[str, dict[str, Any]]:
    """
    Parse target pattern with optional transformations.

    Examples:
        "Title.title" -> ("Title.title", {})
        "Creator.creator_name|name_type=Organizational" -> ("Creator.creator_name", {"name_type": "Organizational"})
        "Date.date|transform=extract_year" -> ("Date.date", {"transform": "extract_year"})
    """
    if "|" not in target:
        return target, {}

    parts = target.split("|", 1)
    path = parts[0]
    transform_str = parts[1]

    transformations = {}

    # Parse transformations (key=value pairs)
    for pair in transform_str.split("|"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            transformations[key.strip()] = value.strip()

    return path, transformations
