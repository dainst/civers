"""
Tests for metadata_extractors/mappers/mapping_adapter.py

mapping_adapter converts a plain {source: target} dict (from YAML config) into
MappingRule dataclass objects. Target strings can carry |key=value transformation
suffixes that are parsed out into a separate transformations dict.
"""

import pytest

from metadata_extractors.mappers.key_parser import PathSegment
from metadata_extractors.mappers.mapping_adapter import MappingRule, parse_mapping_rules


@pytest.mark.unit
class TestParseMappingRules:
    def test_simple_mapping(self):
        rules = parse_mapping_rules({"name": "Title.title"})

        assert len(rules) == 1
        assert rules[0].source_pattern == "name"
        assert rules[0].target_pattern == "Title.title"
        assert rules[0].transformations == {}

    def test_multiple_rules(self):
        mapping = {
            "name": "Title.title",
            "description": "Description.description",
            "author": "Creator.creator_name",
        }
        rules = parse_mapping_rules(mapping)

        assert len(rules) == 3
        sources = [r.source_pattern for r in rules]
        assert "name" in sources
        assert "description" in sources
        assert "author" in sources

    def test_transformation_parsed(self):
        rules = parse_mapping_rules({"author.name": "Creator.creator_name|name_type=Organizational"})

        assert rules[0].target_pattern == "Creator.creator_name"
        assert rules[0].transformations == {"name_type": "Organizational"}

    def test_transform_extract_year(self):
        rules = parse_mapping_rules({"datePublished": "Date.date|transform=extract_year"})

        assert rules[0].target_pattern == "Date.date"
        assert rules[0].transformations == {"transform": "extract_year"}

    def test_multiple_transformations(self):
        rules = parse_mapping_rules({"field": "Target.field|a=1|b=2"})

        assert rules[0].transformations == {"a": "1", "b": "2"}

    def test_empty_dict(self):
        rules = parse_mapping_rules({})

        assert rules == []

    def test_target_segments_parsed(self):
        rules = parse_mapping_rules({"name": "Title.title"})

        assert isinstance(rules[0].target_segments, list)
        assert len(rules[0].target_segments) >= 1
        assert isinstance(rules[0].target_segments[0], PathSegment)

    def test_array_source_pattern_preserved(self):
        rules = parse_mapping_rules({"keywords[*]": "Subject.subject"})

        assert rules[0].source_pattern == "keywords[*]"

    def test_mapping_rule_is_dataclass(self):
        rules = parse_mapping_rules({"name": "Title.title"})

        assert isinstance(rules[0], MappingRule)
