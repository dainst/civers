#!/usr/bin/env python3
"""
Test suite for JSON-LD Extractor functionality.

This test suite focuses specifically on JSON-LD extraction capabilities,
testing the extraction of structured data from HTML documents.
"""

import json
import os
import sys

import pytest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metadata_extractors.base_extractor import ExtractionStatus
from metadata_extractors.extractors.jsonld_extractor import JsonLDExtractor


class TestJsonLDExtractor:
    """Test class for JSON-LD extractor functionality."""

    @pytest.fixture
    def jsonld_extractor(self):
        """Fixture providing a JsonLDExtractor instance."""
        return JsonLDExtractor()

    @pytest.fixture
    def domain_config(self):
        """Basic domain configuration for testing."""
        return {"domain": "test.com", "mapping_config": {}, "extraction_config": {}}

    @pytest.fixture
    def simple_jsonld_html(self):
        """Fixture providing simple HTML with JSON-LD."""
        return """
        <html>
            <head>
                <title>Simple Test Page</title>
                <script type="application/ld+json">
                {
                    "@context": "http://schema.org",
                    "@type": "Dataset",
                    "name": "Test Dataset",
                    "description": "A test dataset for extraction",
                    "author": {
                        "name": "Test Author"
                    }
                }
                </script>
            </head>
            <body>
                <h1>Test Content</h1>
            </body>
        </html>
        """

    @pytest.fixture
    def complex_jsonld_html(self):
        """Fixture providing complex HTML with nested JSON-LD."""
        return """
        <html>
            <head>
                <title>Complex Test Page</title>
                <script type="application/ld+json">
                {
                    "@context": "http://schema.org",
                    "@type": "Dataset",
                    "name": "Arachne Database",
                    "description": "Archaeological object database",
                    "mainEntity": {
                        "@type": "Thing",
                        "headline": "Augustus Statue from Prima Porta",
                        "@id": "https://arachne.dainst.org/entity/1079332",
                        "datePublished": "2012-09-20T10:14:30.000Z",
                        "author": {
                            "name": "Deutsches Archäologisches Institut"
                        },
                        "publisher": {
                            "name": "DAI Publishing"
                        },
                        "spatialCoverage": {
                            "name": "Vatican Museums, Rome",
                            "geo": {
                                "latitude": "41.90225",
                                "longitude": "12.4533"
                            }
                        }
                    },
                    "breadcrumb": {
                        "itemListElement": [
                            {
                                "item": {
                                    "name": "Roman Sculpture"
                                }
                            }
                        ]
                    }
                }
                </script>
            </head>
            <body>
                <h1>Complex Test Content</h1>
            </body>
        </html>
        """

    @pytest.fixture
    def same_class_array_json_ld_html(self):
        """Fixture providing HTML with same class array in JSON-LD."""
        return """
        <html>
            <head>
                <title>Geolocation Array Test</title>
                <script type="application/ld+json">
                {
                    "@context": "http://schema.org",
                    "@type": "Place",
                    "name": "Test Location",
                    "geo":[ {
                        "@type": "GeoCoordinates",
                        "latitude": 40.7128,
                        "longitude": -74.0060
                    },
                    {
                        "@type": "GeoCoordinates",
                        "latitude": 34.0522,
                        "longitude": -118.2437
                    }],
                    "additionalProperty": [
                        {
                            "name": "Region",
                            "value": "North America"
                        },
                        {
                            "name": "Country",
                            "value": "USA"
                        }
                    ]
                }
                </script>
            </head>
            <body>
                <h1>Geolocation Array Test Content</h1>
            </body>
        </html>
        """

    @pytest.fixture
    def arachne_html_content(self, test_sources_dir):
        """Fixture providing Arachne sample HTML content."""
        # test_file_path = os.path.join(
        #     os.path.dirname(__file__),
        #     'test_sources',
        #     'new_arachne_json_ld_sample.html'
        # )
        test_file_path = os.path.join(test_sources_dir, "new_arachne_json_ld_sample.html")
        if os.path.exists(test_file_path):
            with open(test_file_path, encoding="utf-8") as f:
                return f.read()
        else:
            pytest.skip(f"Test file not found: {test_file_path}")

    def test_extractor_initialization(self, jsonld_extractor):
        """Test JsonLDExtractor initialization."""
        assert jsonld_extractor is not None
        assert hasattr(jsonld_extractor, "extract")
        assert jsonld_extractor.get_extractor_type() == "jsonld"

    def test_result_instance(self, jsonld_extractor, simple_jsonld_html, domain_config):
        """Test that extraction returns a Result instance."""
        result = jsonld_extractor.extract(simple_jsonld_html, "https://test.com")

        assert result is not None
        assert hasattr(result, "status")
        assert hasattr(result, "flattened_raw_data")
        assert hasattr(result, "source_url")
        assert hasattr(result, "extraction_type")
        assert isinstance(result.status, ExtractionStatus)
        assert isinstance(result.flattened_raw_data, dict)
        assert result.source_url == "https://test.com"
        assert result.extraction_type == "jsonld"

    def test_extraction_success_simple(self, jsonld_extractor, simple_jsonld_html):
        """Test successful extraction from simple JSON-LD."""
        result = jsonld_extractor.extract(simple_jsonld_html, "https://test.com")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.is_successful()
        assert result.flattened_raw_data is not None
        assert isinstance(result.flattened_raw_data, dict)
        assert result.source_url == "https://test.com"
        assert result.extraction_type == "jsonld"

    def test_extraction_success_complex(self, jsonld_extractor, complex_jsonld_html):
        """Test successful extraction from complex JSON-LD."""
        result = jsonld_extractor.extract(complex_jsonld_html, "https://arachne.dainst.org")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.is_successful()
        assert result.flattened_raw_data is not None
        assert isinstance(result.flattened_raw_data, dict)

    def test_extraction_flattened_keys(self, jsonld_extractor, complex_jsonld_html):
        """Test that extraction produces flattened keys."""
        result = jsonld_extractor.extract(complex_jsonld_html, "https://test.com")

        assert result.is_successful()
        flattened_data = result.flattened_raw_data

        # Check for expected flattened keys (simplified, no type-aware prefixing)
        expected_keys = [
            "name",
            "description",
            "mainEntity.headline",
            "mainEntity.author.name",
            "mainEntity.publisher.name",
            "mainEntity.spatialCoverage.name",
            "mainEntity.spatialCoverage.geo.latitude",
            "mainEntity.spatialCoverage.geo.longitude",
        ]

        for key in expected_keys:
            assert key in flattened_data, f"Expected key '{key}' not found in flattened data"

    def test_extraction_metadata_count(self, jsonld_extractor, complex_jsonld_html):
        """Test that extraction includes metadata count."""
        result = jsonld_extractor.extract(complex_jsonld_html, "https://test.com")

        assert result.is_successful()
        assert "_meta.script_count" in result.flattened_raw_data
        assert result.flattened_raw_data["_meta.script_count"] == 1

    def test_extraction_with_empty_html(self, jsonld_extractor):
        """Test extraction with empty HTML."""
        result = jsonld_extractor.extract("", "https://test.com")

        assert result.status == ExtractionStatus.FAILED
        assert not result.is_successful()

    def test_extraction_with_invalid_html(self, jsonld_extractor):
        """Test extraction with invalid HTML."""
        invalid_html = (
            "<html><head><script type='application/ld+json'>invalid json</script></head></html>"
        )
        result = jsonld_extractor.extract(invalid_html, "https://test.com")

        # Should handle gracefully
        assert result.status in [ExtractionStatus.FAILED, ExtractionStatus.PARTIAL]

    def test_extraction_keys_format(self, jsonld_extractor, complex_jsonld_html):
        """Test that extracted keys follow expected format."""
        result = jsonld_extractor.extract(complex_jsonld_html, "https://test.com")

        assert result.is_successful()
        flattened_data = result.flattened_raw_data

        # All keys should be strings and follow dot notation for nested properties
        for key in flattened_data.keys():
            assert isinstance(key, str)
            if "." in key:
                # Nested keys should not start or end with dot
                assert not key.startswith(".")
                assert not key.endswith(".")

    def test_extraction_values_format(self, jsonld_extractor, simple_jsonld_html):
        """Test that extracted values maintain proper types."""
        result = jsonld_extractor.extract(simple_jsonld_html, "https://test.com")

        assert result.is_successful()
        flattened_data = result.flattened_raw_data

        # Check specific value types
        assert isinstance(flattened_data.get("name"), str)
        assert isinstance(flattened_data.get("description"), str)
        assert isinstance(flattened_data.get("author.name"), str)

    def test_extraction_with_multiple_scripts(self, jsonld_extractor):
        """Test extraction with multiple JSON-LD scripts."""
        html_with_multiple_scripts = """
        <html>
            <head>
                <script type="application/ld+json">{"@type": "Dataset", "name": "Dataset 1"}</script>
                <script type="application/ld+json">{"@type": "Person", "name": "Person 1"}</script>
            </head>
        </html>
        """

        result = jsonld_extractor.extract(html_with_multiple_scripts, "https://test.com")

        assert result.is_successful()
        assert result.flattened_raw_data["_meta.script_count"] == 2

    def test_extraction_performance_timing(self, jsonld_extractor, simple_jsonld_html):
        """Test that extraction includes performance timing."""
        result = jsonld_extractor.extract(simple_jsonld_html, "https://test.com")

        assert result.is_successful()
        assert result.processing_time_seconds is not None
        assert isinstance(result.processing_time_seconds, float)
        assert result.processing_time_seconds >= 0

    def test_extraction_array_handling(self, jsonld_extractor):
        """Test extraction with array structures."""
        html_with_arrays = """
        <html>
            <head>
                <script type="application/ld+json">
                {
                    "@context": "http://schema.org",
                    "authors": [
                        {"name": "Author 1"},
                        {"name": "Author 2"}
                    ],
                    "keywords": ["keyword1", "keyword2", "keyword3"]
                }
                </script>
            </head>
        </html>
        """

        result = jsonld_extractor.extract(html_with_arrays, "https://test.com")

        assert result.is_successful()
        # Arrays should be flattened with index notation
        assert "authors[0].name" in result.flattened_raw_data
        assert "authors[1].name" in result.flattened_raw_data
        assert "keywords[0]" in result.flattened_raw_data

    def test_extraction_with_arachne_sample(self, jsonld_extractor, arachne_html_content):
        """Test extraction with Arachne sample HTML content."""
        result = jsonld_extractor.extract(arachne_html_content, "https://arachne.dainst.org")
        # json dump raw data to file
        with open("arachne_extraction_flattened_data.json", "w", encoding="utf-8") as f:
            json.dump(result.flattened_raw_data, f, indent=2, ensure_ascii=False)

        assert result.is_successful()
        assert result.flattened_raw_data is not None
        assert isinstance(result.flattened_raw_data, dict)

        assert "description" in result.flattened_raw_data
        assert "author[0].name" in result.flattened_raw_data
        assert "author[0].identifier.value" in result.flattened_raw_data
        # Publishers
        assert "publisher[0].name" in result.flattened_raw_data
        assert "publisher[0].identifier.value" in result.flattened_raw_data

    def test_extraction_same_class_array(self, jsonld_extractor, same_class_array_json_ld_html):
        """Test extraction with same class array in JSON-LD."""
        result = jsonld_extractor.extract(same_class_array_json_ld_html, "https://test.com")

        assert result.is_successful()
        assert result.flattened_raw_data is not None
        assert isinstance(result.flattened_raw_data, dict)

        # Check for geolocation array handling (simplified keys)
        assert "geo[0].latitude" in result.flattened_raw_data
        assert "geo[0].longitude" in result.flattened_raw_data
        assert "geo[1].longitude" in result.flattened_raw_data
        assert "geo[1].latitude" in result.flattened_raw_data
        assert "additionalProperty[0].name" in result.flattened_raw_data
        assert "additionalProperty[0].value" in result.flattened_raw_data
        assert "additionalProperty[1].value" in result.flattened_raw_data
        assert "additionalProperty[1].name" in result.flattened_raw_data
