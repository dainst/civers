"""
Domain Service for Civers Archive Web Interface.

This service manages domain configurations for the archive request feature.
It provides matching logic and form data preparation.
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

from configs.models import DomainConfig

logger = logging.getLogger(__name__)


class DomainService:
    """
    Service for matching domain configurations.
    
    This service provides domain management for the archive request feature:
    - Provides domain list for form dropdown
    - Validates URLs against domain patterns
    
    The domain matching logic follows the standard three-tier strategy:
    1. Exact domain match (e.g., "arachne.dainst.org")
    2. Wildcard domain match (e.g., "*.dainst.org")
    3. Default fallback
    """
    
    def __init__(self, domains: List[DomainConfig]):
        """
        Initialize the domain service with pre-loaded domains.
        
        Args:
            domains: List of DomainConfig objects (usually from AppConfig)
        """
        self.domains = domains
        self.is_initialized = True
        logger.info(f"DomainService initialized with {len(self.domains)} domains")
    
    async def initialize(self) -> bool:
        """Compatibility method for lifespan initialization."""
        return True
    
    def get_enabled_domains(self, include_wildcards: bool = True, include_default: bool = False) -> List[DomainConfig]:
        """
        Get list of enabled domains for form dropdown.
        
        Args:
            include_wildcards: Whether to include wildcard patterns (default: True)
            include_default: Whether to include the 'default' fallback (default: False)
        
        Returns:
            List of enabled DomainConfig objects
        """
        result = []
        for domain in self.domains:
            if not domain.enabled:
                continue
            if domain.is_default and not include_default:
                continue
            if domain.is_wildcard and not include_wildcards:
                continue
            result.append(domain)
        
        return result
    
    def get_domain_names_for_dropdown(self) -> List[Dict[str, str]]:
        """
        Get domain names formatted for form dropdown.
        
        Returns:
            List of dicts with 'value' and 'label' keys
        """
        domains = self.get_enabled_domains(include_wildcards=True, include_default=False)
        return [
            {
                "value": domain.name,
                "label": domain.display_name
            }
            for domain in domains
        ]
    
    def match_url_to_domain(self, url: str) -> Optional[DomainConfig]:
        """
        Match a URL to a domain configuration.
        
        Matches using three-tier strategy: Exact → Wildcard → Default.
        
        Args:
            url: URL to match
        
        Returns:
            DomainConfig if matched, None if no match
        """
        if not url or not url.strip():
            return None
        
        # Parse URL to extract domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]
            
            if not domain:
                return None
                
        except Exception:
            return None
        
        # Strategy 1: Exact match
        for domain_info in self.domains:
            if domain_info.enabled and domain_info.name.lower() == domain:
                logger.debug(f"Exact domain match: {domain} → {domain_info.name}")
                return domain_info
        
        # Strategy 2: Wildcard match
        for domain_info in self.domains:
            if domain_info.enabled and domain_info.is_wildcard:
                pattern = domain_info.name.lower().replace("*", "")
                if pattern and domain.endswith(pattern):
                    logger.debug(f"Wildcard domain match: {domain} → {domain_info.name}")
                    return domain_info
        
        # Strategy 3: Default fallback
        for domain_info in self.domains:
            if domain_info.enabled and domain_info.is_default:
                logger.debug(f"Default domain match: {domain} → {domain_info.name}")
                return domain_info
        
        return None
    
    def is_url_supported(self, url: str) -> bool:
        """Check if a URL is supported by any domain configuration."""
        return self.match_url_to_domain(url) is not None
    
    def validate_url_for_domain(self, url: str, expected_domain: str) -> bool:
        """
        Validate that a URL matches the expected domain.
        
        Matches using standard expansion rules.
        
        Args:
            url: URL to validate
            expected_domain: Domain pattern (from dropdown selection)
        
        Returns:
            True if URL matches the expected domain, False otherwise
        """
        if not url or not expected_domain:
            return False
        
        # Parse URL to extract domain
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.lower()
            
            if ":" in url_domain:
                url_domain = url_domain.split(":")[0]
            
            if not url_domain:
                return False
                
        except Exception:
            return False
        
        expected_lower = expected_domain.lower()
        
        # Exact match
        if url_domain == expected_lower:
            return True
        
        # Wildcard match
        if "*" in expected_domain:
            pattern = expected_lower.replace("*", "")
            if pattern and url_domain.endswith(pattern):
                return True
        
        # Default matches everything
        if expected_lower == "default":
            return True
        
        return False
