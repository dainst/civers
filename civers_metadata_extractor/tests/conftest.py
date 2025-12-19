#!/usr/bin/env python3
"""
Comprehensive test configuration and shared fixtures.

This file contains common configurations, fixtures, and utilities
shared across all test modules.
"""

import pytest
import sys
import os
import tempfile

# Ensure component's root is FIRST in path to prevent importing from parent project
_component_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _component_root in sys.path:
    sys.path.remove(_component_root)
sys.path.insert(0, _component_root)

# Set default environment for tests
os.environ.setdefault("CONFIG_ENVIRONMENT", "testing")



# Shared fixtures
@pytest.fixture(scope="session")
def project_root():
    """Fixture providing the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def test_sources_dir():
    """Fixture providing the test sources directory."""
    return os.path.join(os.path.dirname(__file__), 'test_sources')


@pytest.fixture
def sample_domain_configs():
    """Fixture providing sample domain configurations for testing."""
    return {
        'arachne': {
            'name': 'arachne.dainst.org',
            'mappings': {
                'name': 'Title.title',
                'description': 'Description.description',
                'mainEntity.headline': 'Title.title',
                'mainEntity.author.name': 'Creator.creator_name',
                'mainEntity.publisher.name': 'Publisher.publisher',
                'mainEntity.spatialCoverage.name': 'GeoLocation.geo_location_place',
                'mainEntity.spatialCoverage.geo.latitude': 'GeoLocation.geo_location_point.point_latitude',
                'mainEntity.spatialCoverage.geo.longitude': 'GeoLocation.geo_location_point.point_longitude',
                'breadcrumb.itemListElement[*].item.name': 'Subject.subject'
            }
        },
        'generic': {
            'name': 'generic.domain.org',
            'mappings': {
                'name': 'Title.title',
                'description': 'Description.description',
                'author.name': 'Creator.creator_name',
                'keywords[*]': 'Subject.subject'
            }
        }
    }


@pytest.fixture
def arachne_real_data_mapping_config():
    """Fixture providing comprehensive mapping configuration based on real Arachne JSON-LD flattened data."""
    return {
        'name': 'arachne.dainst.org',
        'input_source': 'html_document',
        'mappings': {
            # Basic metadata fields
            'name': 'Title.title',
            'description': 'Description.description',
            '@id': 'Identifier.identifier',
            
            # Date fields
            'datePublished': 'Date.date',
            'dateModified': 'Date.date',
            
            # Author/Creator mappings (using real flattened structure with type info)
            'author[*].Organization.name': 'Creator.creator_name',
            'author[*].Organization.alternateName': 'Creator.creator_name_alternate',
            'author[*].Organization.url': 'Creator.creator_identifier',
            'author[*].Organization.identifier.PropertyValue.value': 'Creator.creator_identifier',
            'author[*].Organization.identifier.PropertyValue.propertyID': 'Creator.creator_identifier_type',
            
            # Publisher mappings (using real flattened structure with type info)
            'publisher[*].Organization.name': 'Publisher.publisher',
            'publisher[*].Organization.alternateName': 'Publisher.publisher_alternate',
            'publisher[*].Organization.url': 'Publisher.publisher_identifier',
            'publisher[*].Organization.identifier.PropertyValue.value': 'Publisher.publisher_identifier',
            'publisher[*].Organization.identifier.PropertyValue.propertyID': 'Publisher.publisher_identifier_type',
            
            # Website/Container information
            'isPartOf.WebSite.name': 'Container.title',
            'isPartOf.WebSite.url': 'Container.identifier',
            
            # Spatial coverage (using real flattened structure)
            'spatialCoverage[].Place.name': 'GeoLocation.geo_location_place',
            'spatialCoverage[].Place.geo.GeoCoordinates.latitude': 'GeoLocation.geo_location_point.point_latitude',
            'spatialCoverage[].Place.geo.GeoCoordinates.longitude': 'GeoLocation.geo_location_point.point_longitude',
            'spatialCoverage[].Place.identifier.PropertyValue.value': 'GeoLocation.geo_location_identifier',
            'spatialCoverage[].Place.identifier.PropertyValue.propertyID': 'GeoLocation.geo_location_identifier_type',
            
            # Temporal coverage (using real flattened structure)
            'temporalCoverage[*].DefinedTerm.name': 'Subject.subject',
            'temporalCoverage[*].DefinedTerm.identifier.PropertyValue.value': 'Subject.subject_identifier',
            'temporalCoverage[*].DefinedTerm.identifier.PropertyValue.propertyID': 'Subject.subject_identifier_type',
            
            # Citations as related identifiers (using real flattened structure)
            'citation[*].CreativeWork.name': 'RelatedIdentifier.related_identifier',
            'citation[*].CreativeWork.identifier.PropertyValue.value': 'RelatedIdentifier.related_identifier',
            'citation[*].CreativeWork.identifier.PropertyValue.propertyID': 'RelatedIdentifier.related_identifier_type',
            
            # Images as format information (direct array values)
            'image[*]': 'Format.format',
            
            # Metadata information
            '_meta.source_url': 'Identifier.source_url',
            '_meta.script_count': 'Identifier.script_count',
            '_meta.extraction_timestamp': 'Date.extraction_timestamp',
        }
    }


@pytest.fixture
def array_mapping_test_config():
    """Fixture providing array mapping configuration for testing different array patterns."""
    return {
        'name': 'array-test.domain.org',
        'input_source': 'html_document',
        'mappings': {
            # Different array mapping patterns for testing
            
            # [*] - Process all array elements
            'author[*].name': 'Creator.creator_name',
            'keywords[*]': 'Subject.subject',
            'citation[*].identifier.value': 'RelatedIdentifier.related_identifier',
            
            # [] - Process first array element only
            'spatialCoverage[].name': 'GeoLocation.geo_location_place',
            'spatialCoverage[].geo.latitude': 'GeoLocation.geo_location_point.point_latitude',
            'spatialCoverage[].geo.longitude': 'GeoLocation.geo_location_point.point_longitude',
            
            # Mixed patterns for different data types
            'publisher[*].name': 'Publisher.publisher',
            'publisher[*].identifier.value': 'Publisher.publisher_identifier',
            'image[*]': 'Format.format',
            'temporalCoverage[*].name': 'Subject.subject',
            
            # Nested array handling
            'author[*].affiliation[*].name': 'Creator.creator_affiliation',
            'contributor[*].identifier[].value': 'Contributor.contributor_identifier',
            
            # Simple mappings for reference
            'name': 'Title.title',
            'description': 'Description.description',
            '@id': 'Identifier.identifier',
            'datePublished': 'Date.date',
        }
    }


@pytest.fixture
def array_mapping_sample_data():
    """Fixture providing sample data for testing array mapping patterns."""
    return {
        # Basic fields
        "name": "Test Archaeological Dataset",
        "description": "Sample dataset for testing array mappings",
        "@id": "https://test.domain.org/dataset/123",
        "datePublished": "2024-01-15T10:00:00.000Z",
        
        # Array fields for testing different patterns
        "author": [
            {
                "name": "Dr. Jane Smith",
                "affiliation": [
                    {"name": "University A"},
                    {"name": "Institute B"}
                ]
            },
            {
                "name": "Prof. John Doe",
                "affiliation": [
                    {"name": "University C"}
                ]
            }
        ],
        
        "publisher": [
            {
                "name": "Academic Press",
                "identifier": {"value": "pub-123"}
            },
            {
                "name": "Research Institute",
                "identifier": {"value": "pub-456"}
            }
        ],
        
        "keywords": ["archaeology", "roman", "pottery", "excavation"],
        
        "spatialCoverage": [
            {
                "name": "Rome, Italy",
                "geo": {
                    "latitude": "41.9028",
                    "longitude": "12.4964"
                }
            },
            {
                "name": "Florence, Italy", 
                "geo": {
                    "latitude": "43.7696",
                    "longitude": "11.2558"
                }
            }
        ],
        
        "temporalCoverage": [
            {"name": "Roman Period"},
            {"name": "Imperial Period"}
        ],
        
        "citation": [
            {
                "name": "Reference A",
                "identifier": {"value": "ref-001"}
            },
            {
                "name": "Reference B", 
                "identifier": {"value": "ref-002"}
            }
        ],
        
        "image": [
            "https://test.domain.org/image1.jpg",
            "https://test.domain.org/image2.jpg",
            "https://test.domain.org/image3.jpg"
        ],
        
        "contributor": [
            {
                "name": "Contributor A",
                "identifier": [
                    {"value": "orcid-001"},
                    {"value": "researcher-id-001"}
                ]
            }
        ]
    }


@pytest.fixture
def arachne_flattened_sample_data():
    """Fixture providing flattened data structure based on real Arachne extraction format."""
    return {
        # Basic fields
        "@context": "http://schema.org",
        "@type": "WebPage",
        "@id": "https://arachne.dainst.org/entity/1079332",
        "name": "Panzerstatue des Augustus von Prima Porta",
        "description": "Resource about cultural objects",
        
        # Date fields
        "dateModified": "2012-09-20T10:14:30.000Z",
        "datePublished": "2012-09-20T10:14:30.000Z",
        
        # Authors (real flattened structure with type information)
        "author[0].@type": "Organization",
        "author[0].Organization.identifier.@type": "PropertyValue",
        "author[0].Organization.identifier.PropertyValue.propertyID": "ror.org",
        "author[0].Organization.identifier.PropertyValue.value": "https://ror.org/041qv0h25",
        "author[0].Organization.name": "Deutsches Archäologisches Institut",
        "author[0].Organization.alternateName": "German Archaeological Institute",
        "author[0].Organization.url": "https://www.dainst.org",
        "author[0].Organization.sameAs[0]": "https://www.wikidata.org/wiki/Q695302",
        
        "author[1].@type": "Organization",
        "author[1].Organization.identifier.@type": "PropertyValue",
        "author[1].Organization.identifier.PropertyValue.propertyID": "ror.org",
        "author[1].Organization.identifier.PropertyValue.value": "https://ror.org/00rcxh774",
        "author[1].Organization.name": "Universität zu Köln",
        "author[1].Organization.alternateName": "University of Cologne",
        "author[1].Organization.url": "http://www.portal.uni-koeln.de/",
        "author[1].Organization.sameAs[0]": "https://www.wikidata.org/wiki/Q54096",
        
        # Publishers (real flattened structure with type information)
        "publisher[0].@type": "Organization",
        "publisher[0].Organization.identifier.@type": "PropertyValue",
        "publisher[0].Organization.identifier.PropertyValue.propertyID": "ror.org",
        "publisher[0].Organization.identifier.PropertyValue.value": "https://ror.org/041qv0h25",
        "publisher[0].Organization.name": "Deutsches Archäologisches Institut",
        "publisher[0].Organization.alternateName": "German Archaeological Institute",
        "publisher[0].Organization.url": "https://www.dainst.org",
        "publisher[0].Organization.sameAs[0]": "https://www.wikidata.org/wiki/Q695302",
        
        "publisher[1].@type": "Organization",
        "publisher[1].Organization.identifier.@type": "PropertyValue",
        "publisher[1].Organization.identifier.PropertyValue.propertyID": "ror.org",
        "publisher[1].Organization.identifier.PropertyValue.value": "https://ror.org/00rcxh774",
        "publisher[1].Organization.name": "Universität zu Köln",
        "publisher[1].Organization.alternateName": "University of Cologne",
        "publisher[1].Organization.url": "http://www.portal.uni-koeln.de/",
        "publisher[1].Organization.sameAs[0]": "https://www.wikidata.org/wiki/Q54096",
        
        # Container/Website information (real flattened structure)
        "isPartOf.@type": "WebSite",
        "isPartOf.WebSite.name": "iDAI.objects/Arachne",
        "isPartOf.WebSite.url": "https://arachne.dainst.org",
        
        # Spatial coverage (real flattened structure with type information)
        "spatialCoverage[0].@type": "Place",
        "spatialCoverage[0].Place.name": "Staat Vatikanstadt, Italien, Musei Vaticani, Braccio Nuovo",
        "spatialCoverage[0].Place.identifier.@type": "PropertyValue",
        "spatialCoverage[0].Place.identifier.PropertyValue.propertyID": "gazetteer.dainst.org",
        "spatialCoverage[0].Place.identifier.PropertyValue.value": 2095222,
        "spatialCoverage[0].Place.geo.@type": "GeoCoordinates",
        "spatialCoverage[0].Place.geo.GeoCoordinates.latitude": "41.90225",
        "spatialCoverage[0].Place.geo.GeoCoordinates.longitude": "12.4533",
        
        # Temporal coverage (real flattened structure with type information)
        "temporalCoverage[0].@type": "DefinedTerm",
        "temporalCoverage[0].DefinedTerm.name": "augusteisch",
        "temporalCoverage[0].DefinedTerm.identifier.@type": "PropertyValue",
        "temporalCoverage[0].DefinedTerm.identifier.PropertyValue.propertyID": "chronontology.dainst.org",
        "temporalCoverage[0].DefinedTerm.identifier.PropertyValue.value": "https://chronontology.dainst.org/period/?",
        
        # Sample citations (real flattened structure with type information)
        "citation[0].@type": "CreativeWork",
        "citation[0].CreativeWork.name": "H. Bruno – P. Arndt – F. Bruckmann (Hrsg.), Griechische und römische Porträts (München 1891–1942)",
        "citation[0].CreativeWork.identifier.@type": "PropertyValue",
        "citation[0].CreativeWork.identifier.PropertyValue.propertyID": "zenon.dainst.org",
        "citation[0].CreativeWork.identifier.PropertyValue.value": "000746500",
        
        "citation[1].@type": "CreativeWork",
        "citation[1].CreativeWork.name": "H. Brunn – F. Bruckmann, Denkmäler griechischer und römischer Skulptur I (München 1902)",
        "citation[1].CreativeWork.identifier.@type": "PropertyValue",
        "citation[1].CreativeWork.identifier.PropertyValue.propertyID": "zenon.dainst.org",
        "citation[1].CreativeWork.identifier.PropertyValue.value": "001369980",
        
        "citation[2].@type": "CreativeWork",
        "citation[2].CreativeWork.name": "W. Helbig, Führer durch die öffentlichen Sammlungen klassischer Altertümer in Rom",
        "citation[2].CreativeWork.identifier.@type": "PropertyValue",
        "citation[2].CreativeWork.identifier.PropertyValue.propertyID": "zenon.dainst.org",
        "citation[2].CreativeWork.identifier.PropertyValue.value": "000001272",
        
        # Sample images (direct array values)
        "image[0]": "https://arachne.dainst.org/data/image/7346407",
        "image[1]": "https://arachne.dainst.org/data/image/7346276",
        "image[2]": "https://arachne.dainst.org/data/image/7346331",
        "image[3]": "https://arachne.dainst.org/data/image/7346375",
        "image[4]": "https://arachne.dainst.org/data/image/7346376",
        
        # Metadata (real extraction metadata)
        "_meta.source_url": "https://arachne.dainst.org",
        "_meta.script_count": 1,
        "_meta.extraction_timestamp": 1754486431.679035
    }


@pytest.fixture
def sample_html_templates():
    """Fixture providing HTML templates for testing."""
    return {
        'simple_jsonld': """
        <html>
            <head>
                <title>{title}</title>
                <script type="application/ld+json">
                {{
                    "@context": "http://schema.org",
                    "@type": "Dataset",
                    "name": "{name}",
                    "description": "{description}"
                }}
                </script>
            </head>
            <body>
                <h1>{title}</h1>
            </body>
        </html>
        """,
        
        'complex_jsonld': """
        <html>
            <head>
                <title>{title}</title>
                <script type="application/ld+json">
                {{
                    "@context": "http://schema.org",
                    "@type": "Dataset",
                    "name": "{name}",
                    "description": "{description}",
                    "mainEntity": {{
                        "headline": "{headline}",
                        "author": {{"name": "{author}"}},
                        "spatialCoverage": {{
                            "name": "{location}",
                            "geo": {{
                                "latitude": "{latitude}",
                                "longitude": "{longitude}"
                            }}
                        }}
                    }}
                }}
                </script>
            </head>
            <body>
                <h1>{title}</h1>
            </body>
        </html>
        """
    }


# Test utilities
class TestDataBuilder:
    """Helper class for building test data."""
    
    @staticmethod
    def build_extraction_result(status="SUCCESS", data=None, extraction_type="jsonld", 
                               source_url="https://test.com", processing_time=0.1):
        """Build an ExtractionResult for testing."""
        from metadata_extractors.base_extractor import ExtractionResult, ExtractionStatus
        
        if data is None:
            data = {"test": "data"}
            
        status_enum = getattr(ExtractionStatus, status)
        
        return ExtractionResult(
            status=status_enum,
            raw_data=data,
            extraction_type=extraction_type,
            source_url=source_url,
            processing_time_seconds=processing_time
        )
    
    @staticmethod
    def build_mapping_result(status="SUCCESS", metadata=None, processing_time=0.1):
        """Build a MappingResult for testing."""
        from metadata_extractors.mappers.flattened_to_intermediate_mapper import MappingResult, MappingStatus
        from models.intermediate_metadata import IntermediateModel
        
        if metadata is None:
            metadata = IntermediateModel()
            
        status_enum = getattr(MappingStatus, status)
        
        return MappingResult(
            status=status_enum,
            intermediate_metadata=metadata,
            processing_time_seconds=processing_time
        )
    
    @staticmethod
    def build_flattened_jsonld_data(**kwargs):
        """Build flattened JSON-LD data for testing."""
        default_data = {
            "name": "Test Dataset",
            "description": "Test description",
            "mainEntity.headline": "Test Headline",
            "mainEntity.author.name": "Test Author",
            "mainEntity.publisher.name": "Test Publisher",
            "mainEntity.spatialCoverage.name": "Test Location",
            "mainEntity.spatialCoverage.geo.latitude": "41.0",
            "mainEntity.spatialCoverage.geo.longitude": "12.0",
            "_meta.script_count": 1
        }
        
        default_data.update(kwargs)
        return default_data


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Custom assertions
def assert_extraction_successful(result):
    """Assert that an extraction result is successful."""
    assert result is not None
    assert result.is_successful()
    assert result.raw_data is not None


def assert_mapping_successful(result):
    """Assert that a mapping result is successful."""
    assert result is not None
    assert result.is_successful()
    assert result.intermediate_metadata is not None


def assert_has_model_instances(metadata, model_type, min_count=1):
    """Assert that metadata has instances of a specific model type."""
    model_collection = getattr(metadata, f"{model_type.lower()}s", None)
    assert model_collection is not None
    assert len(model_collection) >= min_count


@pytest.fixture
def valid_app_config_file():
    """Fixture providing path to the valid test app configuration file."""
    return "tests/test_app_config.yaml"


@pytest.fixture
def invalid_app_config_file():
    """Fixture providing path to an invalid configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def missing_app_config_file():
    """Fixture providing path to a non-existent configuration file."""
    return "/path/to/nonexistent/config.yaml"


@pytest.fixture
def arachne_raw_json_data():
    """Fixture providing the complete raw JSON-LD data from Arachne sample."""
    return {
        "@context": "http://schema.org",
        "@type": "WebPage",
        "@id": "https://arachne.dainst.org/entity/1079332",
        "name": "Panzerstatue des Augustus von Prima Porta",
        "description": "Resource about cultural objects",
        "author": [
            {
                "@type": "Organization",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "ror.org",
                    "value": "https://ror.org/041qv0h25"
                },
                "name": "Deutsches Archäologisches Institut",
                "alternateName": "German Archaeological Institute",
                "url": "https://www.dainst.org",
                "sameAs": [
                    "https://www.wikidata.org/wiki/Q695302"
                ]
            },
            {
                "@type": "Organization",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "ror.org",
                    "value": "https://ror.org/00rcxh774"
                },
                "name": "Universität zu Köln",
                "alternateName": "University of Cologne",
                "url": "http://www.portal.uni-koeln.de/",
                "sameAs": [
                    "https://www.wikidata.org/wiki/Q54096"
                ]
            }
        ],
        "publisher": [
            {
                "@type": "Organization",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "ror.org",
                    "value": "https://ror.org/041qv0h25"
                },
                "name": "Deutsches Archäologisches Institut",
                "alternateName": "German Archaeological Institute",
                "url": "https://www.dainst.org",
                "sameAs": [
                    "https://www.wikidata.org/wiki/Q695302"
                ]
            },
            {
                "@type": "Organization",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "ror.org",
                    "value": "https://ror.org/00rcxh774"
                },
                "name": "Universität zu Köln",
                "alternateName": "University of Cologne",
                "url": "http://www.portal.uni-koeln.de/",
                "sameAs": [
                    "https://www.wikidata.org/wiki/Q54096"
                ]
            }
        ],
        "isPartOf": {
            "@type": "WebSite",
            "name": "iDAI.objects/Arachne",
            "url": "https://arachne.dainst.org",
            "publisher": [
                {
                    "@type": "Organization",
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "ror.org",
                        "value": "https://ror.org/041qv0h25"
                    },
                    "name": "Deutsches Archäologisches Institut",
                    "alternateName": "German Archaeological Institute",
                    "url": "https://www.dainst.org",
                    "sameAs": []
                },
                {
                    "@type": "Organization",
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "ror.org", 
                        "value": "https://ror.org/00rcxh774"
                    },
                    "name": "Universität zu Köln",
                    "alternateName": "University of Cologne",
                    "url": "http://www.portal.uni-koeln.de/",
                    "sameAs": []
                }
            ]
        },
        "dateModified": "2012-09-20T10:14:30.000Z",
        "datePublished": "2012-09-20T10:14:30.000Z",
        "spatialCoverage": [
            {
                "@type": "Place",
                "name": "Staat Vatikanstadt, Italien, Musei Vaticani, Braccio Nuovo",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "gazetteer.dainst.org",
                    "value": 2095222
                },
                "geo": {
                    "@type": "GeoCoordinates",
                    "latitude": "41.90225",
                    "longitude": "12.4533"
                }
            }
        ],
        "temporalCoverage": [
            {
                "@type": "DefinedTerm",
                "name": "augusteisch",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "chronontology.dainst.org",
                    "value": "https://chronontology.dainst.org/period/?"
                }
            }
        ],
        "citation": [
            {
                "@type": "CreativeWork",
                "name": "H. Bruno – P. Arndt – F. Bruckmann (Hrsg.), Griechische und römische Porträts (München 1891–1942)",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "zenon.dainst.org",
                    "value": "000746500"
                }
            },
            {
                "@type": "CreativeWork",
                "name": "H. Brunn – F. Bruckmann, Denkmäler griechischer und römischer Skulptur I (München 1902)",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "zenon.dainst.org",
                    "value": "001369980"
                }
            },
            {
                "@type": "CreativeWork",
                "name": "W. Helbig, Führer durch die öffentlichen Sammlungen klassischer Altertümer in Rom",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "zenon.dainst.org",
                    "value": "000001272"
                }
            }
        ],
        "image": [
            "https://arachne.dainst.org/data/image/7346407",
            "https://arachne.dainst.org/data/image/7346276",
            "https://arachne.dainst.org/data/image/7346331",
            "https://arachne.dainst.org/data/image/7346375",
            "https://arachne.dainst.org/data/image/7346376"
        ]
    }
