"""
Metadata extraction services module.

This module provides clean service implementation with direct ConfigDataModel access:
- MetadataExtractionService: Clean service with minimal components

Components:
- UrlValidator: URL validation and domain checking  

NOTE: DomainConfigManager and HealthMonitor removed - unnecessary complexity.
Services now work directly with ConfigDataModel for clean, simple architecture.
"""

from .metadata_extraction_service_interface import MetadataExtractionServiceInterface
from .metadata_extraction_service import MetadataExtractionService
from .url_validator import UrlValidator

__all__ = [
    'MetadataExtractionServiceInterface',
    'MetadataExtractionService',
    'UrlValidator'
]
