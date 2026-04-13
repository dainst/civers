"""
Refactored MetadataExtractionService - Clean and focused implementation.

This service orchestrates the complete metadata extraction process
using minimal components and direct ConfigDataModel access.
"""

import time
from datetime import datetime
from typing import Any

import httpx

from configs.logging_config import get_logger
from configs.models import ConfigDataModel
from metadata_extractors.extractor_factory import factory as extractor_factory
from metadata_extractors.mappers.flattened_to_intermediate_mapper import (
    FlattenedToIntermediateModelMapper,
    MappingResult,
    MappingStatus,
)
from models import IntermediateMetadata

# Import storage layer components
from storage_layer.storage_manager import StorageManager
from storage_layer.storage_strategy import MultiStorageResult

from .extraction_result import ExtractionResult
from .metadata_extraction_service_interface import MetadataExtractionServiceInterface
from .url_validator import UrlValidator


class ContentFetchError(Exception):
    """Raised when content cannot be fetched from URL."""

    pass


class MetadataExtractionService(MetadataExtractionServiceInterface):
    """
    Clean, focused implementation of metadata extraction service.

    Uses direct ConfigDataModel access - no unnecessary delegation layers.

    Orchestrates the complete extraction process:
    1. Validate URL and check domain support (via ConfigDataModel)
    2. Load domain configuration (via ConfigDataModel)
    3. Process content using mappers
    4. Store metadata using StorageManager (multi-backend)
    5. Return structured results

    Components:
    - ConfigDataModel: Direct access to configuration
    - UrlValidator: URL validation and domain checking
    - ExtractorFactory: Creates domain-specific extractor/mapper pairs
    - StorageManager: Handles multi-backend storage operations
    """

    def __init__(self, config_data_model: ConfigDataModel):
        """
        Initialize the metadata extraction service with minimal components.

        Args:
            config_data_model: Configuration data model instance
        """
        self.logger = get_logger(__name__)

        # Store ConfigDataModel directly - no delegation needed
        self.config_data_model = config_data_model

        # Initialize core components
        self.url_validator = UrlValidator(config_data_model)

        # Initialize the unified mapper (injected directly, not from factory)
        self.mapper = FlattenedToIntermediateModelMapper()
        self.logger.debug("Injected FlattenedToIntermediateModelMapper into service")

        # Initialize storage manager with storage configuration
        storage_config = config_data_model.app.storage
        self.storage_manager = StorageManager(storage_config)  # type: ignore[arg-type]
        self.logger.info(
            f"Initialized StorageManager with {len(self.storage_manager.get_enabled_backends())} backend(s): "
            f"{', '.join(self.storage_manager.get_enabled_backends())}"
        )


        self.logger.info(
            "MetadataExtractionService initialized with injected mapper and storage manager"
        )

    async def extract_metadata(
        self,
        url: str,
        request_id: str,
        html_content: str | None = None,
        document_url: str | None = None,
    ) -> ExtractionResult:
        """
        Extract metadata from document URL or provided HTML content.

        Content Sources (one required):
        1. document_url - Download HTML from this URL (e.g., storage service) 
        2. html_content - Use provided HTML string

        Args:
            url: Source URL for context and validation
            request_id: Unique identifier for this request
            html_content: Optional HTML content
            document_url: Optional URL to download HTML document from
        """
        start_time = time.time()

        try:
            self.logger.info(f"Starting metadata extraction for {url} (request: {request_id})")

            # Validate that either document_url or html_content is provided
            if not document_url and not html_content:
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message="Either 'document_url' or 'html_content' must be provided",
                    error_type="MissingContentError",
                    failed_stage="content_validation",
                    source_url=url,
                )



            # Step 1: URL validation and domain support check (directly using ConfigDataModel)
            url_validation = self.url_validator.validate_url(url)
            if not url_validation.get("valid", False):
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message=f"Invalid URL: {url_validation.get('reason', 'Unknown validation error')}",
                    error_type="URLValidationError",
                    failed_stage="url_validation",
                    source_url=url,
                )

            if not url_validation.get("domain_supported", False):
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message=f"Domain not supported: {url_validation.get('reason', 'Unknown domain error')}",
                    error_type="DomainNotSupportedError",
                    failed_stage="domain_validation",
                    source_url=url,
                )

            # Get domain configuration
            domain = url_validation.get("domain")
            if not domain:
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message="Could not extract domain from URL",
                    error_type="DomainExtractionError",
                    failed_stage="domain_extraction",
                    source_url=url,
                )

            # Get domain configuration directly from ConfigDataModel
            domain_config = self.config_data_model.get_domain_config_as_dict(domain)
            if not domain_config:
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message=f"Failed to load configuration for domain: {domain}",
                    error_type="ConfigurationError",
                    failed_stage="configuration_loading",
                    source_url=url,
                )

            # Step 2: Content handling - document_url or html_content (both are optional but at least one required)
            if document_url:
                # Priority 1: Download from document_url
                self.logger.info(f"Downloading HTML from document_url: {document_url}")
                try:
                    content = await self._fetch_content_from_url(document_url)
                    self.logger.info(
                        f"Successfully downloaded {len(content)} characters from document URL"
                    )
                except ContentFetchError as e:
                    processing_time = time.time() - start_time
                    return ExtractionResult.failure_result(
                        request_id=request_id,
                        processing_time=processing_time,
                        error_message=f"Failed to download document from {document_url}: {str(e)}",
                        error_type="ContentFetchError",
                        failed_stage="document_download",
                        source_url=document_url,
                    )
            else:
                # Priority 2: Use provided HTML content (already validated that this exists)
                content = html_content
                self.logger.info(
                    f"Using provided HTML content for {url} ({len(content)} characters)"
                )

            # Step 3: Process content (existing logic enhanced)
            metadata, mapping_result, error_msg, error_type, raw_data = await self._process_content(
                content, domain_config, url
            )

            if not metadata:
                processing_time = time.time() - start_time
                return ExtractionResult.failure_result(
                    request_id=request_id,
                    processing_time=processing_time,
                    error_message=error_msg or "Failed to extract metadata from content",
                    error_type=error_type or "MetadataExtractionError",
                    failed_stage="content_processing",
                    source_url=url,
                    raw_data=raw_data,
                )

            processing_time = time.time() - start_time

            # Create successful result
            result = ExtractionResult.success_result(
                request_id=request_id,
                processing_time=processing_time,
                intermediate_metadata=metadata,
                domain_used=domain,
                mappers_used=self._get_used_mappers(domain_config),  # Track which mappers were used
                artifacts_created=[],
                source_url=url,
            )

            # Generate JSON output if metadata was extracted (pass mapping_result for completeness calculation)
            json_output_path = await self._generate_json_output(result, mapping_result)  # type: ignore[arg-type]
            if json_output_path:
                result.artifacts_created.append(json_output_path)
                # Add json_output_path to result for workflow tracking
                result.json_output_path = json_output_path
                self.logger.info(f"Generated JSON output: {json_output_path}")

            self.logger.info(
                f"Successfully extracted metadata from {url} in {processing_time:.2f}s"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Error extracting metadata from {url}: {e}")
            return ExtractionResult.failure_result(
                request_id=request_id,
                processing_time=processing_time,
                error_message=str(e),
                error_type=type(e).__name__,
                failed_stage="unexpected_error",
                source_url=url,
            )

    def validate_url(self, url: str) -> dict[str, Any]:
        """
        Validate if a URL can be processed by this extraction service.
        Delegates to UrlValidator component.

        Args:
            url: The URL to validate

        Returns:
            Dict containing validation results
        """
        return self.url_validator.validate_url(url)


    # Private helper methods for core extraction logic

    async def _process_content(
        self, content: str, domain_config: dict[str, Any], source_url: str
    ) -> tuple[
        IntermediateMetadata | None,
        MappingResult | None,
        str | None,
        str | None,
        dict[str, Any] | None,
    ]:
        """
        Process content using the consolidated extractor factory.

        Args:
            content: Content to process (HTML, JSON, XML, etc.)
            domain_config: Domain configuration
            source_url: Source URL

        Returns:
            Tuple of (IntermediateMetadata, MappingResult, error_message, error_type, raw_data)
        """
        try:
            # Get appropriate extractor from factory (factory only creates extractors now)
            extractor = extractor_factory.get_extractor(domain_config)

            if not extractor:
                return (
                    None,
                    None,
                    "Failed to create extractor for content",
                    "ExtractorCreationError",
                    None,
                )

            # Extract raw data
            extraction_result = extractor.extract(content, source_url)

            if not extraction_result.is_successful():
                error_msg = extraction_result.error_message or "Extraction failed"
                self.logger.warning(f"Extraction failed: {error_msg}")
                return (
                    None,
                    None,
                    f"Extraction failed: {error_msg}",
                    "ExtractionStoreError",
                    extraction_result.flattened_raw_data,
                )

            # Map to intermediate model using injected mapper
            mapping_result = self.mapper.map_to_intermediate(
                extraction_result.flattened_raw_data, domain_config, source_url
            )

            if (
                mapping_result.status != MappingStatus.SUCCESS
                or not mapping_result.intermediate_metadata
            ):
                error_msg = (
                    mapping_result.errors[0]
                    if mapping_result.errors
                    else "No intermediate metadata generated"
                )
                self.logger.warning(f"Mapping failed: {error_msg}")
                return (
                    None,
                    mapping_result,
                    f"Mapping failed: {error_msg}",
                    "MappingError",
                    extraction_result.flattened_raw_data,
                )

            self.logger.debug(
                f"Successfully processed content using {extractor.get_extractor_type()} extractor and injected mapper"
            )
            return (
                mapping_result.intermediate_metadata,
                mapping_result,
                None,
                None,
                extraction_result.flattened_raw_data,
            )

        except Exception as e:
            self.logger.error(f"Error processing content: {e}", exc_info=True)
            return None, None, str(e), type(e).__name__, None

    async def _fetch_content_from_url(self, url: str, timeout_seconds: int = 30) -> str:
        """
        Fetch HTML content from URL with robust error handling.

        Args:
            url: URL to fetch content from
            timeout_seconds: Request timeout in seconds

        Returns:
            HTML content string

        Raises:
            ContentFetchError: If content cannot be fetched
        """
        try:
            self.logger.info(f"Fetching content from URL: {url}")
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Validate content type
                content_type = response.headers.get("content-type", "")
                if not any(ct in content_type.lower() for ct in ["html", "xml"]):
                    self.logger.warning(f"Unexpected content type: {content_type}")

                self.logger.info(f"Successfully fetched {len(response.text)} characters from {url}")
                return response.text

        except httpx.RequestError as e:
            raise ContentFetchError(f"HTTP request failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise ContentFetchError(f"HTTP error {e.response.status_code}: {e}") from e
        except Exception as e:
            raise ContentFetchError(f"Unexpected error fetching content: {e}") from e

    def _get_used_mappers(self, domain_config: dict[str, Any]) -> list[str]:
        """
        Extract mapper information from domain configuration.

        Since we now have only one universal mapper, this always returns
        'flattened_to_intermediate'.

        Args:
            domain_config: Domain configuration dictionary

        Returns:
            List containing the universal mapper name
        """
        return ["flattened_to_intermediate"]

    async def _generate_json_output(
        self,
        result: ExtractionResult,
        mapping_result: MappingResult,
        output_dir: str = "output/metadata",
    ) -> str | None:
        """
        Generate comprehensive JSON output and store using StorageManager.

        Uses StorageManager to store metadata across all enabled backends
        (e.g., local file, CIVERS API, S3, etc.).

        Args:
            result: ExtractionResult to save
            mapping_result: MappingResult with completeness statistics
            output_dir: Directory to save JSON files (used for filename generation)

        Returns:
            Primary storage location (path/URL) or None if all backends failed
        """
        try:
            # Generate descriptive filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain_name = result.domain_used.replace(".", "_") if result.domain_used else "unknown"
            filename = f"metadata_{domain_name}_{result.request_id}_{timestamp}.json"

            # Prepare comprehensive output structure
            output_data = {
                "metadata_extraction_result": {
                    "request_information": {
                        "request_id": result.request_id,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "processing_time_seconds": result.processing_time_seconds,
                        "domain_used": result.domain_used,
                        "mappers_used": result.mappers_used,
                    },
                    "extraction_status": {
                        "success": result.success,
                        "error_message": result.error_message,
                        "error_type": result.error_type,
                        "failed_stage": result.failed_stage,
                    }
                    if not result.success
                    else {"success": True, "artifacts_created": result.artifacts_created},
                },
                "intermediate_metadata": {
                    "datacite_model": result.intermediate_metadata.model_dump()
                    if result.intermediate_metadata
                    else None,
                    "model_validation": {
                        "is_valid": result.intermediate_metadata
                        is not None,  # If metadata exists, validation passed
                        "validation_errors": [],  # No errors if we reached this point
                        "completeness_score": self._calculate_completeness_score(mapping_result),
                    },
                },
                "extraction_analytics": {
                    "total_fields_available": mapping_result.mapped_fields_count
                    + mapping_result.skipped_fields_count,
                    "mapped_fields_count": mapping_result.mapped_fields_count,
                    "skipped_fields_count": mapping_result.skipped_fields_count,
                    "field_mapping_statistics": self._generate_mapping_statistics(mapping_result),
                    "skip_reason_breakdown": self._generate_skip_reason_breakdown(mapping_result),
                    "quality_metrics": {
                        "completeness": self._calculate_completeness_score(mapping_result),
                        "mapping_coverage": mapping_result.mapped_fields_count
                        / (mapping_result.mapped_fields_count + mapping_result.skipped_fields_count)
                        if (
                            mapping_result.mapped_fields_count + mapping_result.skipped_fields_count
                        )
                        > 0
                        else 0.0,
                        "success_rate": 1.0 if result.success else 0.0,
                    },
                },
                "system_metadata": {
                    "extraction_service_version": getattr(self.config_data_model.app, "version", "unknown"),
                    "configuration_version": getattr(self.config_data_model.app, "version", "1.0"),
                    "output_format_version": "1.0",
                    "generated_by": "CIVERS Metadata Extractor",
                },
            }

            # Store metadata using StorageManager (multi-backend)
            self.logger.info(f"Storing metadata via StorageManager: {filename}")

            storage_result: MultiStorageResult = await self.storage_manager.store_metadata(
                data=output_data,
                request_id=result.request_id,
                url=result.source_url or "unknown",
                filename=filename,
            )

            if storage_result.overall_success:
                successful_backends = storage_result.get_successful_backends()
                self.logger.info(
                    f"✅ Metadata stored successfully to {len(successful_backends)} backend(s): "
                    f"{', '.join(successful_backends)}"
                )

                # Dynamically populate artifacts_created with all successful locations
                for res in storage_result.results:
                    if res.success and res.storage_location:
                        # Add location to artifacts if not already present
                        if res.storage_location not in result.artifacts_created:
                            result.artifacts_created.append(res.storage_location)

                # Log failed backends if any
                failed_backends = storage_result.get_failed_backends()
                if failed_backends:
                    self.logger.warning(
                        f"⚠️ Failed to store to {len(failed_backends)} backend(s): {', '.join(failed_backends)}"
                    )

                # Return primary location (preferably local_file)
                return storage_result.primary_location
            else:
                # All backends failed
                self.logger.error(f"❌ All storage backends failed for request {result.request_id}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to store metadata: {e}")
            return None

    def _calculate_completeness_score(self, mapping_result: MappingResult) -> float:
        """
        Calculate metadata completeness score based on mapping results.

        Args:
            mapping_result: MappingResult with field statistics

        Returns:
            Completeness score from 0.0 to 1.0
        """
        if not mapping_result:
            return 0.0

        total_fields = mapping_result.mapped_fields_count + mapping_result.skipped_fields_count
        if total_fields == 0:
            return 0.0

        return mapping_result.mapped_fields_count / total_fields

    def _generate_mapping_statistics(self, mapping_result: MappingResult) -> dict[str, Any]:
        """
        Generate detailed mapping statistics from mapping result.

        Args:
            mapping_result: MappingResult with field statistics

        Returns:
            Dictionary with mapping statistics
        """
        return {
            "successful_mappings": mapping_result.mapped_fields_count,
            "failed_mappings": mapping_result.skipped_fields_count,
            "total_attempted": mapping_result.mapped_fields_count
            + mapping_result.skipped_fields_count,
            "success_rate": mapping_result.mapped_fields_count
            / (mapping_result.mapped_fields_count + mapping_result.skipped_fields_count)
            if (mapping_result.mapped_fields_count + mapping_result.skipped_fields_count) > 0
            else 0.0,
            "processing_time_seconds": mapping_result.processing_time_seconds,
        }

    def _generate_skip_reason_breakdown(self, mapping_result: MappingResult) -> dict[str, Any]:
        """
        Generate breakdown of reasons why fields were skipped.

        Args:
            mapping_result: MappingResult with skipped field details

        Returns:
            Dictionary with skip reason analysis
        """
        if not mapping_result.skipped_fields_details:
            return {}

        # Group by reason
        reason_counts: dict[str, int] = {}
        for skipped in mapping_result.skipped_fields_details:
            reason = skipped.get("reason", "Unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        # Calculate percentages
        total_skipped = len(mapping_result.skipped_fields_details)
        reason_breakdown = {}
        for reason, count in reason_counts.items():
            reason_breakdown[reason] = {
                "count": count,
                "percentage": (count / total_skipped * 100) if total_skipped > 0 else 0.0,
            }

        return {
            "total_skipped_fields": total_skipped,
            "reasons": reason_breakdown,
            "most_common_reason": max(reason_counts, key=lambda k: reason_counts[k])
            if reason_counts
            else None,
        }
