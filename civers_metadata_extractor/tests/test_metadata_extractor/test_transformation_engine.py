"""
Tests for metadata_extractors/mappers/transformation_engine.py

TransformationEngine takes flattened input data and a list of MappingRule objects
and produces a nested dict. It supports:
- Direct field mapping (name → Title.title)
- Wildcard array indices (keywords[*] → Subject[*].subject)
- Value transforms: extract_year, constant, map
- Static side-loaded fields (|name_type=Organizational sets a sibling field)

Tests use parse_mapping_rules() to build rules, so they also serve as light
integration tests for the mapping_adapter + engine path.
"""

import pytest

from metadata_extractors.mappers.mapping_adapter import parse_mapping_rules
from metadata_extractors.mappers.transformation_engine import TransformationEngine


@pytest.mark.unit
class TestTransformationEngine:
    def test_simple_flat_mapping(self):
        rules = parse_mapping_rules({"name": "Title.title"})
        engine = TransformationEngine(rules)

        result = engine.transform({"name": "Test Title"})

        assert result["Title"]["title"] == "Test Title"

    def test_nested_target_path(self):
        rules = parse_mapping_rules({"author": "Creator.creator_name"})
        engine = TransformationEngine(rules)

        result = engine.transform({"author": "Jane Doe"})

        assert result["Creator"]["creator_name"] == "Jane Doe"

    def test_multiple_fields_mapped(self):
        rules = parse_mapping_rules({
            "name": "Title.title",
            "description": "Description.description",
        })
        engine = TransformationEngine(rules)

        result = engine.transform({"name": "My Title", "description": "My Desc"})

        assert result["Title"]["title"] == "My Title"
        assert result["Description"]["description"] == "My Desc"

    def test_no_matching_rule_produces_empty(self):
        rules = parse_mapping_rules({"name": "Title.title"})
        engine = TransformationEngine(rules)

        result = engine.transform({"unrelated_key": "value"})

        assert result == {}

    def test_empty_input_produces_empty(self):
        rules = parse_mapping_rules({"name": "Title.title"})
        engine = TransformationEngine(rules)

        result = engine.transform({})

        assert result == {}

    def test_array_wildcard_mapping_two_elements(self):
        # Target must also use [*] notation to produce a list in the output.
        # Without [*] in the target, each source value would overwrite the previous one.
        rules = parse_mapping_rules({"keywords[*]": "Subject[*].subject"})
        engine = TransformationEngine(rules)

        result = engine.transform({"keywords[0]": "archaeology", "keywords[1]": "roman"})

        assert "Subject" in result
        subjects = result["Subject"]
        assert isinstance(subjects, list)
        assert len(subjects) == 2

    def test_extract_year_transformation(self):
        rules = parse_mapping_rules({"datePublished": "Date.date|transform=extract_year"})
        engine = TransformationEngine(rules)

        result = engine.transform({"datePublished": "2024-01-15"})

        assert result["Date"]["date"] == 2024

    def test_extract_year_from_full_iso_string(self):
        rules = parse_mapping_rules({"datePublished": "Date.date|transform=extract_year"})
        engine = TransformationEngine(rules)

        result = engine.transform({"datePublished": "2019-03-15T10:00:00.000Z"})

        assert result["Date"]["date"] == 2019

    def test_static_sibling_field_from_transformation(self):
        # |name_type=Organizational sets Creator.name_type alongside Creator.creator_name
        rules = parse_mapping_rules({"author.name": "Creator.creator_name|name_type=Organizational"})
        engine = TransformationEngine(rules)

        result = engine.transform({"author.name": "DAI"})

        assert result["Creator"]["creator_name"] == "DAI"
        assert result["Creator"]["name_type"] == "Organizational"

    def test_with_real_arachne_data(self, arachne_real_data_mapping_config, arachne_flattened_sample_data):
        mapping_dict = arachne_real_data_mapping_config["mappings"]
        rules = parse_mapping_rules(mapping_dict)
        engine = TransformationEngine(rules)

        result = engine.transform(arachne_flattened_sample_data)

        assert isinstance(result, dict)
        assert len(result) > 0
