"""
Tests for metadata_extractors/mappers/model_constructor.py

ModelConstructor takes a nested dict produced by TransformationEngine and builds a
validated Pydantic IntermediateMetadata instance. Key behaviours:
- Remaps class-name keys (Title, Creator, Publisher) to Pydantic field names (titles, creators, publisher)
- Wraps a single dict in a list when the model field expects list[T]
- Unwraps a single-item list when the model field expects a scalar
- Removes empty {} entries from lists (artifacts of sparse array mapping)

IntermediateMetadata has strict required fields, so all test inputs must include:
  Creator, Title, Publisher, publication_year, resource_type.
"""

import pytest

from metadata_extractors.mappers.model_constructor import ModelConstructor
from models.intermediate_metadata import IntermediateMetadata


@pytest.fixture
def minimal_valid_data():
    """Minimal nested dict that satisfies all IntermediateMetadata required fields."""
    return {
        "Creator": {"creator_name": "Test Creator"},
        "Title": {"title": "Test Title"},
        "Publisher": {"publisher": "Test Publisher"},
        "publication_year": 2024,
        "resource_type": {"resource_type_general": "Dataset"},
    }


@pytest.mark.unit
class TestModelConstructor:
    def test_construct_with_title(self, minimal_valid_data):
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert isinstance(result, IntermediateMetadata)
        assert len(result.titles) == 1
        assert result.titles[0].title == "Test Title"

    def test_construct_with_creator(self, minimal_valid_data):
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert isinstance(result, IntermediateMetadata)
        assert len(result.creators) == 1
        assert result.creators[0].creator_name == "Test Creator"

    def test_construct_with_multiple_creators(self, minimal_valid_data):
        minimal_valid_data["Creator"] = [
            {"creator_name": "Jane Doe"},
            {"creator_name": "John Smith"},
        ]
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert len(result.creators) == 2
        names = [c.creator_name for c in result.creators]
        assert "Jane Doe" in names
        assert "John Smith" in names

    def test_construct_publisher(self, minimal_valid_data):
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert result.publisher.publisher == "Test Publisher"

    def test_construct_publication_year(self, minimal_valid_data):
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert result.publication_year == 2024

    def test_build_static_method(self, minimal_valid_data):
        result = ModelConstructor.build(IntermediateMetadata, minimal_valid_data)

        assert isinstance(result, IntermediateMetadata)
        assert result.titles[0].title == "Test Title"

    def test_cleans_empty_dicts_from_list(self, minimal_valid_data):
        # An empty dict in a Creator list is a mapping artifact and should be removed
        minimal_valid_data["Creator"] = [
            {"creator_name": "Jane"},
            {},  # artifact of sparse mapping
        ]
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert len(result.creators) == 1
        assert result.creators[0].creator_name == "Jane"

    def test_single_publisher_unwrapped_from_list(self, minimal_valid_data):
        # Publisher is a scalar field — if data arrives as a list, first element is used
        minimal_valid_data["Publisher"] = [{"publisher": "Unwrapped Publisher"}]
        constructor = ModelConstructor()

        result = constructor.construct(minimal_valid_data)

        assert result.publisher.publisher == "Unwrapped Publisher"
