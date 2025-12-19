# archive_services/archive_service_interface.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from configs.models import DomainConfig


class ArchiveServiceInterface(ABC):
    """
    Interface for archive services that handle web content archiving.
    
    This interface defines the contract for any archive service implementation,
    enabling dependency injection and strategy pattern usage across the application.
    Different implementations can provide varying archiving strategies, storage backends,
    or optimization approaches while maintaining the same interface.
    """

    @abstractmethod
    async def create_archive(self, url: str, request_id: str, priority: int = 1) -> Dict[str, Any]:
        """
        Create an archive for the given URL.
        
        Args:
            url: The URL to archive
            request_id: Unique identifier for this request
            priority: Priority level (1-10, where 1 is highest priority)
            
        Returns:
            Dict containing:
                - success: bool - Whether archiving succeeded
                - archive_path: str - Path to the created archive (if successful)
                - request_id: str - Echo of the request ID
                - processing_time_seconds: float - Time taken to process
                - error: str - Error message (if failed)
                - artifacts: List[str] - List of created artifact files (optional)
                
        Raises:
            Exception: If archiving fails due to configuration or system errors
        """
        pass

    @abstractmethod
    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate if a URL can be archived by this service.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing:
                - valid: bool - Whether URL is valid and supported
                - domain_supported: bool - Whether the domain has configuration
                - reason: str - Explanation if not valid/supported
                - domain_config: DomainConfig - Domain configuration (if supported)
        """
        pass

    @abstractmethod
    def get_supported_domains(self) -> List[str]:
        """
        Get list of domain names supported by this archive service.
        
        Returns:
            List of domain names (e.g., ['example.com', 'arachne.dainst.org'])
        """
        pass

    @abstractmethod
    def get_domain_config(self, domain_name: str) -> DomainConfig:
        """
        Get the configuration for a specific domain.
        
        Args:
            domain_name: The domain name to get configuration for
            
        Returns:
            DomainConfig object for the domain
            
        Raises:
            ValueError: If domain is not supported
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the archive service.
        
        Returns:
            Dict containing:
                - healthy: bool - Overall health status
                - service_name: str - Name of the service
                - version: str - Service version
                - details: Dict - Additional health information
                - checks: Dict - Individual component health checks
        """
        pass
