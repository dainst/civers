"""
URL validation component.

Handles URL format validation, domain extraction, and scheme checking
for the metadata extraction service.

Works directly with ConfigDataModel - no unnecessary delegation.
"""

from typing import Dict, Any
from urllib.parse import urlparse

from configs.models import ConfigDataModel
from configs.logging_config import get_logger


class UrlValidator:
    """
    Validates URLs and checks domain support.
    
    Works directly with ConfigDataModel for clean, simple architecture.
    
    Responsibilities:
    - URL format validation
    - Domain extraction from URLs
    - Scheme validation (http/https)
    - Domain support checking via ConfigDataModel
    """
    
    def __init__(self, config_data_model: ConfigDataModel):
        """
        Initialize the URL validator.
        
        Args:
            config_data_model: Configuration data model instance
        """
        self.config_data_model = config_data_model
        self.logger = get_logger(__name__)
        
        # Supported URL schemes
        self.supported_schemes = ['http', 'https']
        
        self.logger.info("UrlValidator initialized")
    
    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate if a URL can be processed by the extraction service.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing:
                - valid: bool - Whether URL is valid and supported
                - domain_supported: bool - Whether the domain has configuration
                - reason: str - Explanation if not valid/supported
                - domain: str - Extracted domain (if valid)
        """
        try:
            # Basic URL format validation
            format_result = self._validate_url_format(url)
            if not format_result['valid']:
                return format_result
            
            # Extract domain from URL
            domain = self.parse_domain_from_url(url)
            if not domain:
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': 'Could not extract domain from URL'
                }
            
            # Check domain support using ConfigDataModel directly
            domain_supported = self.config_data_model.is_domain_supported(domain)
            if domain_supported:
                return {
                    'valid': True,
                    'domain_supported': True,
                    'reason': 'URL is valid and domain is supported',
                    'domain': domain
                }
            else:
                return {
                    'valid': True,
                    'domain_supported': False,
                    'reason': f'Domain {domain} is not configured',
                    'domain': domain
                }
            
        except Exception as e:
            self.logger.error(f"Error validating URL {url}: {e}")
            return {
                'valid': False,
                'domain_supported': False,
                'reason': f'Validation error: {str(e)}'
            }
    
    def parse_domain_from_url(self, url: str) -> str:
        """
        Extract domain name from URL.
        
        Args:
            url: URL to parse
            
        Returns:
            Domain name or empty string if parsing fails
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception as e:
            self.logger.error(f"Error parsing domain from URL {url}: {e}")
            return ""
    
    def _validate_url_format(self, url: str) -> Dict[str, Any]:
        """
        Validate basic URL format and structure.
        
        Args:
            url: URL to validate
            
        Returns:
            Dict with validation results
        """
        try:
            # Check if URL is a non-empty string
            if not url or not isinstance(url, str):
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': 'URL must be a non-empty string'
                }
            
            # Parse URL
            parsed = urlparse(url)
            
            # Check basic URL structure
            if not parsed.scheme or not parsed.netloc:
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': 'URL must have scheme and domain'
                }
            
            # Check allowed schemes
            if not self._validate_scheme(parsed.scheme):
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': f'Only {", ".join(self.supported_schemes)} schemes are supported'
                }
            
            return {
                'valid': True,
                'domain_supported': None,  # Will be determined later
                'reason': 'URL format is valid'
            }
            
        except Exception as e:
            self.logger.error(f"Error validating URL format for {url}: {e}")
            return {
                'valid': False,
                'domain_supported': False,
                'reason': f'URL format validation error: {str(e)}'
            }
    
    def _validate_scheme(self, scheme: str) -> bool:
        """
        Validate URL scheme.
        
        Args:
            scheme: URL scheme to validate
            
        Returns:
            True if scheme is supported
        """
        return scheme.lower() in self.supported_schemes
    
    def is_valid_domain_format(self, domain: str) -> bool:
        """
        Check if domain has valid format.
        
        Args:
            domain: Domain to validate
            
        Returns:
            True if domain format is valid
        """
        try:
            # Basic domain format check
            if not domain or not isinstance(domain, str):
                return False
            
            # Domain should contain at least one dot
            if '.' not in domain:
                return False
            
            # Domain should not start or end with dot
            if domain.startswith('.') or domain.endswith('.'):
                return False
            
            # Domain should not contain invalid characters
            invalid_chars = [' ', '/', '\\', '?', '#']
            if any(char in domain for char in invalid_chars):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating domain format for {domain}: {e}")
            return False
    
