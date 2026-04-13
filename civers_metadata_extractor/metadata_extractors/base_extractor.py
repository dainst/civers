"""
Base Extractor Interface

This module defines the abstract base class and common data structures for all
metadata extractors in the system. All specific extractors (JSON-LD, meta tags,
CSS selectors) must implement this interface.

The base extractor follows the strategy pattern, allowing different extraction
approaches while maintaining a consistent interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ExtractionStatus(StrEnum):
    """Status of the extraction operation"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some data extracted but with warnings
    NOT_IMPLEMENTED = "not_implemented"  # Feature not yet implemented


@dataclass
class ExtractionResult:
    """
    Result of a metadata extraction operation.

    This standardized result format ensures all extractors return consistent
    data structures for downstream processing and mapping.
    """

    status: ExtractionStatus
    flattened_raw_data: dict[str, Any]  # Raw extracted data before mapping
    extraction_type: str  # Type of extraction used (jsonld, meta_tags, css_selectors)
    source_url: str
    processing_time_seconds: float
    warnings: list[str] | None = None  # Non-fatal issues during extraction
    error_message: str | None = None  # Error details if status is FAILED
    metadata_count: int = 0  # Number of metadata fields extracted

    def __post_init__(self):
        """Initialize warnings list if None"""
        if self.warnings is None:
            self.warnings = []

    def add_warning(self, warning: str) -> None:
        """Add a warning message to the result"""
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)

    def is_successful(self) -> bool:
        """Check if extraction was successful or partially successful"""
        return self.status in [ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL]


class BaseExtractor(ABC):
    """
    Abstract base class for all metadata extractors.

    This class defines the contract that all specific extractors must implement.
    It follows the strategy pattern, allowing different extraction strategies
    while maintaining a consistent interface.

    Extractors are responsible for:
    1. Parsing HTML content for their specific data source
    2. Extracting raw metadata according to their strategy
    3. Returning standardized ExtractionResult

    Extractors do NOT perform mapping to the intermediate model - that's
    handled by separate mapper classes.
    """

    @abstractmethod
    def extract(self, html_content: str, source_url: str) -> ExtractionResult:
        """
        Extract metadata from HTML content.

        This is the main extraction method that each extractor must implement.
        It should parse the HTML content, extract relevant metadata according
        to the extractor's strategy, and return a standardized result.

        Args:
            html_content: The HTML content to extract metadata from
            source_url: The source URL for context and validation

        Returns:
            ExtractionResult containing the extracted raw metadata

        Raises:
            Exception: If extraction fails due to critical errors
        """
        pass


    @abstractmethod
    def get_extractor_type(self) -> str:
        """
        Get the type identifier for this extractor.

        This should match the mapper type in domain configuration.

        Returns:
            String identifier for this extractor type
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(type='{self.get_extractor_type()}')"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type='{self.get_extractor_type()}')"
