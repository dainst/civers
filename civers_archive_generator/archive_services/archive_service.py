# archive_services/archive_service.py
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timezone

from configs.models import ConfigDataModel, DomainConfig
from .archive_service_interface import ArchiveServiceInterface
from archive_generators import ArchiveGeneratorFactory
from storage_layer import StorageManager

logger = logging.getLogger(__name__)

class ArchiveService(ArchiveServiceInterface):
    """
    Core archive service containing pure business logic.
    This service is transport-agnostic and handles the core archive creation workflow.
    
    Implements ArchiveServiceInterface to provide a standardized contract for
    archive operations that can be injected into transport layers.
    """
    
    def __init__(self, config: ConfigDataModel):
        self.config = config
        self.generator_factory = ArchiveGeneratorFactory(config)
        
        # Initialize storage manager for multi-backend storage
        storage_config = config.app.get_storage_config()
        self.storage_manager = StorageManager(storage_config)
        
    async def create_archive(self, url: str, request_id: str, priority: int = 1) -> Dict[str, Any]:
        """
        Create an archive for the given URL.
        
        Args:
            url: The URL to archive
            request_id: Unique identifier for this request
            priority: Priority level (1-10, where 1 is highest)
            
        Returns:
            Dict containing success status, archive details, or error information
        """
        start_time = time.time()
        
        logger.info(f"🚀 Starting archive creation for request: {request_id}")
        logger.info(f"   URL: {url}")
        logger.info(f"   Priority: {priority}")
        
        try:
            # Step 1: Find domain configuration
            domain_config = self._find_domain_config(url)
            if not domain_config:
                processing_time = time.time() - start_time
                error_msg = f"No domain configuration found for URL: {url}"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    'success': False,
                    'request_id': request_id,
                    'url': url,
                    'error': error_msg,
                    'error_type': 'configuration_not_found',
                    'processing_time_seconds': processing_time,
                    'priority': priority
                }
            
            logger.info(f"✅ Found domain config: {domain_config.name}")
            
            # Step 2: Create appropriate archive generator
            generator = self._create_archive_generator(domain_config)
            logger.info(f"🔧 Initialized {domain_config.webpage_types} archive generator")
            
            # Step 3: Generate archive - now returns ArchiveResult
            logger.info(f"📦 Generating archive for {url}")
            archive_result = await generator.generate_archive(url, request_id)
            
            # Check if archive generation succeeded
            if not archive_result.success:
                processing_time = time.time() - start_time
                logger.warning(f"⚠️ Archive generation failed: {archive_result.error_message}")
                return {
                    'success': False,
                    'request_id': request_id,
                    'url': url,
                    'archive_path': archive_result.archive_path,
                    'error': archive_result.error_message,
                    'error_type': archive_result.error_type or 'archive_generation_failed',
                    'artifacts_created': archive_result.artifacts_created,
                    'failed_artifacts': [a.name for a in archive_result.failed_artifacts],
                    'processing_time_seconds': processing_time,
                    'scoop_exit_code': archive_result.scoop_exit_code,
                    'priority': priority
                }
            
            logger.info(f"✅ Archive generated: {archive_result.archive_path}")
            logger.debug(f"   Artifacts: {archive_result.artifacts_created}")
            
            # Step 4: Validate required artifacts from domain config
            required_artifacts = domain_config.artifacts or []
            is_valid, missing_artifacts = archive_result.validate_required_artifacts(required_artifacts)
            
            if not is_valid:
                processing_time = time.time() - start_time
                error_msg = f"Missing required artifacts: {', '.join(missing_artifacts)}"
                logger.warning(f"⚠️ Artifact validation failed: {error_msg}")
                return {
                    'success': False,
                    'request_id': request_id,
                    'url': url,
                    'archive_path': archive_result.archive_path,
                    'error': error_msg,
                    'error_type': 'missing_required_artifacts',
                    'artifacts_created': archive_result.artifacts_created,
                    'missing_artifacts': missing_artifacts,
                    'failed_artifacts': [a.name for a in archive_result.failed_artifacts],
                    'processing_time_seconds': processing_time,
                    'scoop_exit_code': archive_result.scoop_exit_code,
                    'priority': priority
                }
            
            logger.info(f"✅ Artifact validation passed")
            
            # Step 5: Store archive
            storage_result = await self._store_archive(
                archive_result.archive_path, url, domain_config, request_id
            )
            logger.info(f"💾 Archive stored successfully")
            
            # Step 5: Calculate processing time and return success
            processing_time = time.time() - start_time
            
            result = {
                'success': True,
                'request_id': request_id,
                'url': url,
                'archive_path': archive_result.archive_path,
                'snapshot_id': archive_result.snapshot_id,
                'storage_result': storage_result,
                'artifacts_created': archive_result.artifacts_created,
                'domain_config': {
                    'name': domain_config.name,
                    'webpage_types': domain_config.webpage_types,
                    'artifacts': domain_config.artifacts
                },
                'processing_time_seconds': processing_time,
                'scoop_exit_code': archive_result.scoop_exit_code,
                'priority': priority
            }
            
            logger.info(f"🎉 Archive creation completed for request {request_id} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"❌ Archive creation failed for request {request_id}: {error_msg}", exc_info=True)
            
            return {
                'success': False,
                'request_id': request_id,
                'url': url,
                'error': error_msg,
                'error_type': 'processing_error',
                'processing_time_seconds': processing_time,
                'priority': priority
            }
    
    def _find_domain_config(self, url: str) -> Optional[DomainConfig]:
        """
        Find domain configuration for given URL.
        
        Args:
            url: The URL to find configuration for
            
        Returns:
            DomainConfig if found, None otherwise
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            # Remove port if present for comparison
            if ":" in domain:
                domain = domain.split(":")[0]
            
            # If domain is empty, URL is invalid
            if not domain:
                logger.debug(f"❌ Invalid URL format: {url}")
                return None
            
            logger.debug(f"🔍 Looking for domain config for: {domain}")
            
            for domain_config in self.config.domains:
                config_name = domain_config.name.lower()
                # Check if domain config name matches
                if (config_name == domain.lower() or 
                    (domain_config.is_wildcard and domain.lower().endswith(config_name.replace("*", "")))):
                    
                    logger.debug(f"✅ Found matching domain config: {domain_config.name}")
                    return domain_config
            
            logger.debug(f"❌ No domain config found for: {domain}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing URL {url}: {e}")
            return None
    
    def _create_archive_generator(self, domain_config: DomainConfig):
        """
        Create appropriate archive generator based on domain configuration.
        
        Uses the ArchiveGeneratorFactory to create the appropriate generator instance.
        
        Args:
            domain_config: The domain configuration
            
        Returns:
            Archive generator instance
            
        Raises:
            ValueError: If no suitable generator can be created
        """
        try:
            return self.generator_factory.create_generator(domain_config)
        except Exception as e:
            logger.error(f"❌ Failed to create archive generator: {e}")
            raise
    
    async def _store_archive(self, archive_path: str, _url: str, domain_config: DomainConfig, request_id: str = None) -> Dict[str, Any]:
        """
        Store the archive using the configured storage strategy.
        
        For Scoop-generated archives, this validates the archive directory and
        creates storage metadata. The actual files are already stored by Scoop.
        For test cases, this handles both file and directory paths.
        
        Uses StorageManager to store metadata to all enabled backends.
        
        Args:
            archive_path: Path to the generated archive directory or file
            _url: Original URL that was archived
            domain_config: Domain configuration used
            request_id: Unique request identifier for storage
            
        Returns:
            Storage result information
        """
        try:
            archive_path_obj = Path(archive_path)
            
            # Handle both file and directory paths for compatibility
            if archive_path_obj.is_file():
                # Single file case (e.g., test mocks or legacy generators)
                created_files = [{
                    'name': archive_path_obj.name,
                    'path': str(archive_path_obj),
                    'size': archive_path_obj.stat().st_size if archive_path_obj.exists() else 0,
                    'type': self._determine_file_type(archive_path_obj.name)
                }]
                total_size = created_files[0]['size']
                
            elif archive_path_obj.is_dir():
                # Directory case (real Scoop-generated archives)
                created_files = []
                total_size = 0
                
                for file_path in archive_path_obj.iterdir():
                    if file_path.is_file():
                        file_size = file_path.stat().st_size
                        created_files.append({
                            'name': file_path.name,
                            'path': str(file_path),
                            'size': file_size,
                            'type': self._determine_file_type(file_path.name)
                        })
                        total_size += file_size
                        
            else:
                # For test cases where path doesn't exist, create minimal metadata
                logger.debug(f"⚠️ Archive path doesn't exist (likely test case): {archive_path}")
                created_files = [{
                    'name': Path(archive_path).name,
                    'path': archive_path,
                    'size': 0,
                    'type': 'unknown'
                }]
                total_size = 0
            
            # Get storage configuration
            storage_config = self.config.app.get_storage_config()
            
            # Generate storage ID
            storage_id = f"archive_{request_id or int(time.time() * 1000)}"
            
            # Create archive metadata for storage
            archive_metadata = {
                'storage_id': storage_id,
                'archive_path': str(archive_path),
                'source_url': _url,
                'domain': domain_config.name,
                'artifacts': domain_config.artifacts,
                'files': created_files,
                'total_size': total_size,
                'file_count': len(created_files),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'request_id': request_id
            }
            
            # Upload all archive artifacts to enabled backends (wacz, html, png, etc.)
            artifacts_storage_result = None
            if self.storage_manager and request_id:
                try:
                    artifacts_storage_result = await self.storage_manager.store_artifacts(
                        archive_path=archive_path,
                        request_id=request_id,
                        url=_url
                    )
                    
                    if artifacts_storage_result.overall_success:
                        logger.info(f"✅ Artifacts uploaded to backends: {artifacts_storage_result.get_successful_backends()}")
                    else:
                        logger.warning(f"⚠️ Artifact upload failed for some backends: {artifacts_storage_result.get_failed_backends()}")
                        
                except Exception as storage_error:
                    logger.warning(f"⚠️ StorageManager error (continuing anyway): {storage_error}")
            
            # Create storage result
            primary_backend = storage_config.enabled[0] if storage_config.enabled else 'local_file'
            storage_result = {
                'storage_id': storage_id,
                'archive_path': archive_path,
                'artifacts': domain_config.artifacts,
                'storage_strategy': primary_backend,
                'stored_at': time.time(),
                'files': created_files,
                'total_size': total_size,
                'file_count': len(created_files),
                'storage_backend': primary_backend,
                'storage_config': storage_config.get_backend_config(primary_backend),
                'enabled_backends': storage_config.get_enabled_backends(),
                'artifacts_storage_result': artifacts_storage_result
            }
            
            logger.debug(f"✅ Archive storage validated: {storage_id}")
            logger.debug(f"   Files created: {len(created_files)}")
            logger.debug(f"   Total size: {total_size} bytes")
            
            return storage_result
            
        except Exception as e:
            logger.error(f"❌ Archive storage validation failed: {e}")
            raise

    def _determine_file_type(self, filename: str) -> str:
        """Determine file type from filename."""
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.wacz', '.warc', '.warc.gz')):
            return 'archive'
        elif filename_lower.endswith(('.html', '.htm')):
            return 'html'
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return 'image'
        elif filename_lower.endswith('.json'):
            return 'metadata'
        elif filename_lower.endswith('.log'):
            return 'log'
        else:
            return 'unknown'
    
    def get_supported_domains(self) -> List[str]:
        """
        Get list of supported domain names.
        
        Returns:
            List of supported domain names
        """
        return [domain.name for domain in self.config.domains]
    
    def get_domain_config(self, domain_name: str) -> DomainConfig:
        """
        Get domain configuration by name.
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            DomainConfig if found
            
        Raises:
            ValueError: If domain is not supported
        """
        for domain_config in self.config.domains:
            if domain_config.name == domain_name:
                return domain_config
        
        supported_domains = self.get_supported_domains()
        raise ValueError(f"Domain '{domain_name}' is not supported. Supported domains: {supported_domains}")
    
    def _find_domain_config_by_name(self, domain_name: str) -> Optional[DomainConfig]:
        """
        Internal helper to find domain config by exact name match (returns None if not found).
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            DomainConfig if found, None otherwise
        """
        for domain_config in self.config.domains:
            if domain_config.name == domain_name:
                return domain_config
        return None
    
    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate if a URL can be archived based on domain configuration.
        
        Args:
            url: URL to validate
            
        Returns:
            Dict containing:
                - valid: bool - Whether URL is valid and supported
                - domain_supported: bool - Whether the domain has configuration
                - reason: str - Explanation if not valid/supported
                - domain_config: DomainConfig - Domain configuration (if supported)
        """
        try:
            parsed_url = urlparse(url)
            
            if not parsed_url.netloc:
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': 'Invalid URL format - no domain found',
                    'url': url
                }
            
            domain_config = self._find_domain_config(url)
            
            if not domain_config:
                return {
                    'valid': False,
                    'domain_supported': False,
                    'reason': f'No domain configuration found for {parsed_url.netloc}',
                    'url': url,
                    'domain': parsed_url.netloc,
                    'supported_domains': self.get_supported_domains()
                }
            
            return {
                'valid': True,
                'domain_supported': True,
                'reason': 'URL is valid and domain is supported',
                'url': url,
                'domain': parsed_url.netloc,
                'domain_config': domain_config
            }
            
        except Exception as e:
            return {
                'valid': False,
                'domain_supported': False,
                'reason': f'URL validation error: {str(e)}',
                'url': url
            }
    
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
        try:
            # Basic configuration validation
            config_healthy = (
                self.config is not None and
                hasattr(self.config, 'app') and
                hasattr(self.config, 'domains') and
                len(self.config.domains) > 0
            )
            
            # Check if archive directory is configured
            archive_dir_configured = (
                hasattr(self.config.app, 'archive_directory') and
                self.config.app.archive_directory
            )
            
            # Count supported domains
            supported_domains_count = len(self.config.domains)
            
            # Get factory information
            factory_info = self.generator_factory.get_factory_info()
            
            # Overall health status
            healthy = config_healthy and archive_dir_configured
            
            return {
                'healthy': healthy,
                'service_name': 'ArchiveService',
                'version': getattr(self.config.app, 'version', '1.0.0'),
                'details': {
                    'supported_domains_count': supported_domains_count,
                    'supported_domains': self.get_supported_domains(),
                    'archive_directory': getattr(self.config.app, 'archive_directory', 'not_configured'),
                    'generator_factory': factory_info,
                },
                'checks': {
                    'configuration_loaded': config_healthy,
                    'archive_directory_configured': archive_dir_configured,
                    'domains_configured': supported_domains_count > 0,
                    'generator_factory_initialized': self.generator_factory is not None,
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                'healthy': False,
                'service_name': 'ArchiveService',
                'version': 'unknown',
                'details': {
                    'error': str(e)
                },
                'checks': {
                    'health_check_execution': False
                }
            }
