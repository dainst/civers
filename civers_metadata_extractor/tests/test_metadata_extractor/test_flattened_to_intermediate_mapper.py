"""
Tests for metadata_extractors/mappers/flattened_to_intermediate_mapper.py

FlattenedToIntermediateModelMapper orchestrates the full mapping pipeline:
  1. Parse YAML mapping rules from domain config
  2. TransformationEngine: flattened dict → nested dict
  3. ModelConstructor: nested dict → IntermediateMetadata (Pydantic)
  4. Add source_url as identifier if none present

All DataCite required fields (publication_year, resource_type_general, creators,
titles, publisher) must be covered by explicit mapping rules. Missing required
fields surface as a FAILED MappingResult — no silent defaults are injected.

Returns a MappingResult with status ("success"/"failed"), the model, and statistics.
"""

import pytest

from metadata_extractors.mappers.flattened_to_intermediate_mapper import (
    FlattenedToIntermediateModelMapper,
    MappingStatus,
)
from models.intermediate_metadata import IntermediateMetadata


@pytest.fixture
def mapper():
    return FlattenedToIntermediateModelMapper()


@pytest.fixture
def complete_domain_config():
    """Domain config that covers all required DataCite fields."""
    return {
        "name": "test.example.org",
        "mappings": {
            "name": "Title.title",
            "author": "Creator.creator_name",
            "publisher": "Publisher.publisher",
            "datePublished": "publication_year|transform=extract_year",
            "@type": "ResourceType.resource_type_general|constant=Dataset",
        },
    }


@pytest.fixture
def complete_input():
    """Flattened input that satisfies all required fields in complete_domain_config."""
    return {
        "name": "Test Item",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "datePublished": "2024-03-15",
        "@type": "Dataset",
    }


@pytest.mark.unit
class TestFlattenedToIntermediateModelMapper:
    def test_successful_mapping(self, mapper, complete_domain_config, complete_input):
        result = mapper.map_to_intermediate(complete_input, complete_domain_config, "https://test.example.org")

        assert result.status == MappingStatus.SUCCESS
        assert isinstance(result.intermediate_metadata, IntermediateMetadata)

    def test_publication_year_mapped_from_date(self, mapper, complete_domain_config, complete_input):
        result = mapper.map_to_intermediate(complete_input, complete_domain_config, "https://test.example.org")

        assert result.status == MappingStatus.SUCCESS
        assert result.intermediate_metadata.publication_year == 2024

    def test_resource_type_general_mapped_as_constant(self, mapper, complete_domain_config, complete_input):
        result = mapper.map_to_intermediate(complete_input, complete_domain_config, "https://test.example.org")

        assert result.status == MappingStatus.SUCCESS
        assert result.intermediate_metadata.resource_type.resource_type_general == "Dataset"

    def test_missing_publication_year_returns_failed(self, mapper):
        # Config without publication_year mapping → Pydantic ValidationError → FAILED
        config = {
            "mappings": {
                "name": "Title.title",
                "author": "Creator.creator_name",
                "publisher": "Publisher.publisher",
                "@type": "ResourceType.resource_type_general|constant=Dataset",
            }
        }
        result = mapper.map_to_intermediate(
            {"name": "T", "author": "A", "publisher": "P", "@type": "X"},
            config,
            "https://test.example.org",
        )

        assert result.status == MappingStatus.FAILED
        assert len(result.errors) > 0

    def test_missing_resource_type_returns_failed(self, mapper):
        # Config without resource_type mapping → Pydantic ValidationError → FAILED
        config = {
            "mappings": {
                "name": "Title.title",
                "author": "Creator.creator_name",
                "publisher": "Publisher.publisher",
                "datePublished": "publication_year|transform=extract_year",
            }
        }
        result = mapper.map_to_intermediate(
            {"name": "T", "author": "A", "publisher": "P", "datePublished": "2024-01-01"},
            config,
            "https://test.example.org",
        )

        assert result.status == MappingStatus.FAILED
        assert len(result.errors) > 0

    def test_missing_mappings_key_returns_failed(self, mapper):
        # No "mappings" key → empty rules → required fields absent → FAILED
        result = mapper.map_to_intermediate(
            {"name": "Test"},
            {"name": "test.example.org"},
            "https://test.example.org",
        )

        assert result.status == MappingStatus.FAILED

    def test_source_url_added_as_identifier(self, mapper, complete_domain_config, complete_input):
        source_url = "https://test.example.org/item/42"

        result = mapper.map_to_intermediate(complete_input, complete_domain_config, source_url)

        assert result.status == MappingStatus.SUCCESS
        assert result.intermediate_metadata.identifier is not None
        assert result.intermediate_metadata.identifier.identifier == source_url

    def test_successful_mapping_with_multiple_creators(self, mapper):
        domain_config = {
            "mappings": {
                "name": "Title.title",
                "author[*].name": "Creator[*].creator_name",
                "publisher": "Publisher.publisher",
                "datePublished": "publication_year|transform=extract_year",
                "@type": "ResourceType.resource_type_general|constant=Dataset",
            }
        }
        raw_data = {
            "name": "An Archaeological Record",
            "author[0].name": "Jane Doe",
            "author[1].name": "John Smith",
            "publisher": "DAI Press",
            "datePublished": "2023-06-01",
            "@type": "Dataset",
        }

        result = mapper.map_to_intermediate(raw_data, domain_config, "https://test.example.org/1")

        assert result.status == MappingStatus.SUCCESS
        assert len(result.intermediate_metadata.creators) == 2

    def test_exception_on_bad_config_returns_failed(self, mapper):
        result = mapper.map_to_intermediate({"name": "Test"}, None, "https://test.example.org")

        assert result.status == MappingStatus.FAILED
        assert len(result.errors) > 0

    def test_source_fields_count_populated(self, mapper, complete_domain_config, complete_input):
        result = mapper.map_to_intermediate(complete_input, complete_domain_config, "https://test.example.org")

        assert result.status == MappingStatus.SUCCESS
        assert result.source_fields_count == len(complete_input)

    def test_failed_result_has_no_metadata(self, mapper):
        result = mapper.map_to_intermediate({"name": "Test"}, None, "https://test.example.org")

        assert result.intermediate_metadata is None
        assert result.mapped_fields_count == 0
