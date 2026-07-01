"""
Tests for metadata_extraction_services/metadata_extraction_service.py

MetadataExtractionService is the main orchestrator. Each request goes through:
  1. Content presence check  — fail if neither html_content nor document_url provided
  2. URL validation           — fail if format invalid or scheme unsupported
  3. Domain support check     — fail if domain not in config
  4. Domain config lookup     — fail if config not found
  5. Content fetch            — if document_url provided, download via httpx
  6. _process_content         — extractor + mapper → IntermediateMetadata
  7. _generate_json_output    — store via StorageManager, return artifact path

Mock strategy:
- ConfigDataModel: Mock with pre-configured url_validator and domain config responses
- ExtractorFactory: Mock via patch of the module-level `factory` singleton
- FlattenedToIntermediateModelMapper: Mock on the service instance
- StorageManager: Mock on the service instance
- httpx.AsyncClient: Mock via pytest-httpx (HTTPXMock fixture)
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from civers_common import ConfigurationError

from metadata_extraction_services.metadata_extraction_service import (
    ContentFetchError,
    MetadataExtractionService,
)
from metadata_extractors.mappers.flattened_to_intermediate_mapper import (
    MappingResult,
    MappingStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """ConfigDataModel mock where arachne.dainst.org is the only supported domain."""
    config = Mock()
    config.app.storage = Mock()
    config.app.storage.backend = "local_file"
    config.app.storage.backends = {"local_file": Mock(base_path="/tmp/test_storage")}
    return config


@pytest.fixture
def service(mock_config):
    """Service with mocked storage and url_validator, no real Kafka or filesystem."""
    with patch("metadata_extraction_services.metadata_extraction_service.StorageManager"):
        svc = MetadataExtractionService(mock_config)

    # Replace url_validator with a controllable mock
    svc.url_validator = Mock()
    # Replace mapper and storage_manager with mocks
    svc.mapper = Mock()
    svc.storage_manager = Mock()
    svc.storage_manager.get_enabled_backends.return_value = ["local_file"]
    return svc


def _url_valid_supported(domain="arachne.dainst.org"):
    return {"valid": True, "domain_supported": True, "reason": "ok", "domain": domain}


def _url_valid_unsupported(domain="unknown.com"):
    return {"valid": True, "domain_supported": False, "reason": "not configured", "domain": domain}


def _url_invalid():
    return {"valid": False, "domain_supported": False, "reason": "bad scheme"}


def _domain_config(domain="arachne.dainst.org"):
    return {
        "name": domain,
        "extractor": "jsonld",
        "mappings": {
            "name": "Title.title",
            "author": "Creator.creator_name",
            "publisher": "Publisher.publisher",
            "datePublished": "publication_year|transform=extract_year",
            "@type": "ResourceType.resource_type_general|constant=Dataset",
        },
    }


def _successful_extractor_result():
    result = Mock()
    result.is_successful.return_value = True
    result.flattened_raw_data = {"name": "Test", "author": "Jane"}
    result.error_message = None
    return result


def _successful_mapping_result():
    from models.intermediate_metadata import (
        Creator,
        IntermediateMetadata,
        Publisher,
        ResourceType,
        ResourceTypeGeneral,
        Title,
    )
    metadata = IntermediateMetadata(
        creators=[Creator(creator_name="Jane Doe")],
        titles=[Title(title="Test Title")],
        publisher=Publisher(publisher="Test Pub"),
        publication_year=2024,
        resource_type=ResourceType(resource_type_general=ResourceTypeGeneral.DATASET),
    )
    result = Mock(spec=MappingResult)
    result.status = MappingStatus.SUCCESS
    result.intermediate_metadata = metadata
    result.errors = []
    result.mapped_fields_count = 3
    result.source_fields_count = 5
    result.skipped_fields_count = 2
    result.skipped_fields_details = []
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.unit
class TestExtractMetadata:
    async def test_no_content_provided_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()

        result = await service.extract_metadata(
            url="https://arachne.dainst.org/entity/1",
            request_id="req-001",
        )

        assert result.success is False
        assert result.failed_stage == "content_validation"

    async def test_invalid_url_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_invalid()

        result = await service.extract_metadata(
            url="ftp://bad.url",
            request_id="req-002",
            html_content="<html></html>",
        )

        assert result.success is False
        assert result.failed_stage == "url_validation"

    async def test_unsupported_domain_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_unsupported()

        result = await service.extract_metadata(
            url="https://unknown.com/page",
            request_id="req-003",
            html_content="<html></html>",
        )

        assert result.success is False
        assert result.failed_stage == "domain_validation"

    async def test_domain_config_not_found_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()
        service.config_data_model.resolve_domain.side_effect = ConfigurationError(
            "Domain not configured"
        )

        result = await service.extract_metadata(
            url="https://arachne.dainst.org/entity/1",
            request_id="req-004",
            html_content="<html></html>",
        )

        assert result.success is False
        assert result.failed_stage == "configuration_loading"

    async def test_extractor_not_found_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()
        service.config_data_model.resolve_domain.return_value.model_dump.return_value = (
            _domain_config()
        )

        with patch(
            "metadata_extraction_services.metadata_extraction_service.extractor_factory"
        ) as mock_factory:
            mock_factory.get_extractor.return_value = None

            result = await service.extract_metadata(
                url="https://arachne.dainst.org/entity/1",
                request_id="req-005",
                html_content="<html></html>",
            )

        assert result.success is False
        assert result.failed_stage == "content_processing"

    async def test_extraction_failure_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()
        service.config_data_model.resolve_domain.return_value.model_dump.return_value = (
            _domain_config()
        )

        failed_extractor_result = Mock()
        failed_extractor_result.is_successful.return_value = False
        failed_extractor_result.error_message = "parse error"
        failed_extractor_result.flattened_raw_data = {}

        mock_extractor = Mock()
        mock_extractor.extract.return_value = failed_extractor_result

        with patch(
            "metadata_extraction_services.metadata_extraction_service.extractor_factory"
        ) as mock_factory:
            mock_factory.get_extractor.return_value = mock_extractor

            result = await service.extract_metadata(
                url="https://arachne.dainst.org/entity/1",
                request_id="req-006",
                html_content="<html></html>",
            )

        assert result.success is False
        assert result.failed_stage == "content_processing"

    async def test_mapping_failure_returns_failure(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()
        service.config_data_model.resolve_domain.return_value.model_dump.return_value = (
            _domain_config()
        )

        mock_extractor = Mock()
        mock_extractor.extract.return_value = _successful_extractor_result()

        failed_mapping = Mock(spec=MappingResult)
        failed_mapping.status = MappingStatus.FAILED
        failed_mapping.intermediate_metadata = None
        failed_mapping.errors = ["Pydantic validation error"]
        service.mapper.map_to_intermediate.return_value = failed_mapping

        with patch(
            "metadata_extraction_services.metadata_extraction_service.extractor_factory"
        ) as mock_factory:
            mock_factory.get_extractor.return_value = mock_extractor

            result = await service.extract_metadata(
                url="https://arachne.dainst.org/entity/1",
                request_id="req-007",
                html_content="<html></html>",
            )

        assert result.success is False
        assert result.failed_stage == "content_processing"

    async def test_successful_extraction_with_html(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()
        service.config_data_model.resolve_domain.return_value.model_dump.return_value = (
            _domain_config()
        )

        mock_extractor = Mock()
        mock_extractor.extract.return_value = _successful_extractor_result()
        mock_extractor.get_extractor_type.return_value = "jsonld"

        service.mapper.map_to_intermediate.return_value = _successful_mapping_result()

        # _generate_json_output uses storage_manager — mock it to return None (no artifact)
        with patch.object(service, "_generate_json_output", new=AsyncMock(return_value=None)):
            with patch(
                "metadata_extraction_services.metadata_extraction_service.extractor_factory"
            ) as mock_factory:
                mock_factory.get_extractor.return_value = mock_extractor

                result = await service.extract_metadata(
                    url="https://arachne.dainst.org/entity/1",
                    request_id="req-008",
                    html_content="<html><head></head><body>content</body></html>",
                )

        assert result.success is True
        assert result.domain_used == "arachne.dainst.org"


@pytest.mark.asyncio
@pytest.mark.unit
class TestFetchContentFromUrl:
    async def test_request_error_raises_content_fetch_error(self, service):
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.RequestError("connection refused", request=Mock())
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ContentFetchError, match="HTTP request failed"):
                await service._fetch_content_from_url("https://arachne.dainst.org/entity/1")

    async def test_http_status_error_raises_content_fetch_error(self, service):
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "404 not found", request=Mock(), response=mock_response
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ContentFetchError, match="HTTP error 404"):
                await service._fetch_content_from_url("https://arachne.dainst.org/entity/1")


@pytest.mark.unit
class TestValidateUrl:
    def test_delegates_to_url_validator(self, service):
        service.url_validator.validate_url.return_value = _url_valid_supported()

        result = service.validate_url("https://arachne.dainst.org/entity/1")

        service.url_validator.validate_url.assert_called_once_with(
            "https://arachne.dainst.org/entity/1"
        )
        assert result["valid"] is True
