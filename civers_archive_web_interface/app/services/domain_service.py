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
            domain_with_port = parsed.netloc.lower()
            
            # Clean domain without port for fallback matching
            domain_without_port = domain_with_port.split(":")[0] if ":" in domain_with_port else domain_with_port
            
            if not domain_without_port:
                return None
                
        except Exception:
            return None
        
        # Helper to check if a candidate domain matches a configured domain
        def check_match(candidate: str, config: DomainConfig) -> bool:
            # Exact match
            if config.name.lower() == candidate:
                return True
            # Wildcard match
            if config.is_wildcard:
                pattern = config.name.lower().replace("*", "")
                if pattern and candidate.endswith(pattern):
                    return True
            return False

        # Strategy: Try exact/wildcard match with port, then without port
        for domain_info in self.domains:
            if not domain_info.enabled:
                continue
                
            # Skip default here, check last
            if domain_info.is_default:
                continue
                
            # Check matches
            if check_match(domain_with_port, domain_info):
                logger.debug(f"Domain match (with port): {domain_with_port} → {domain_info.name}")
                return domain_info
                
            if domain_with_port != domain_without_port and check_match(domain_without_port, domain_info):
                logger.debug(f"Domain match (without port): {domain_without_port} → {domain_info.name}")
                return domain_info
        
        # Strategy 3: Default fallback
        for domain_info in self.domains:
            if domain_info.enabled and domain_info.is_default:
                logger.debug(f"Default domain match: {domain_with_port} → {domain_info.name}")
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
            domain_with_port = parsed.netloc.lower()
            domain_without_port = domain_with_port.split(":")[0] if ":" in domain_with_port else domain_with_port
            
            if not domain_without_port:
                return False
                
        except Exception:
            return False
        
        expected_lower = expected_domain.lower()
        
        # Helper for validation
        def check_valid(candidate: str) -> bool:
            # Exact match
            if candidate == expected_lower:
                return True
            # Wildcard match
            if "*" in expected_domain:
                pattern = expected_lower.replace("*", "")
                if pattern and candidate.endswith(pattern):
                    return True
            return False
            
        # Check both with and without port
        if check_valid(domain_with_port):
            return True
        if domain_with_port != domain_without_port and check_valid(domain_without_port):
            return True
        
        # Default matches everything
        if expected_lower == "default":
            return True
        
        return False
