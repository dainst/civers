# archive_services/archive_service.py
import asyncio
import ipaddress
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiofiles

from configs.models import ConfigDataModel, DomainConfig
from .archive_service_interface import ArchiveServiceInterface
from archive_generators import ArchiveGeneratorFactory, ArchiveResult, ArtifactResult, ArtifactStatus
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
        Create an archive for the given URL by orchestrating multiple generators.
        """
        start_time = datetime.now()
        start_time_ts = time.time()
        
        logger.info(f"🚀 Starting archive creation for request: {request_id}")
        logger.info(f"   URL: {url}")
        
        try:
            # Step 1: Find domain configuration
            domain_config = self._find_domain_config(url)
            if not domain_config:
                processing_time = time.time() - start_time_ts
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
            
            # Step 2: SSRF Protection
            try:
                await self._validate_url_for_ssrf(url)
            except ValueError as e:
                processing_time = time.time() - start_time_ts
                logger.error(f"🚨 SSRF Protection: {e}")
                return {
                    'success': False,
                    'request_id': request_id,
                    'url': url,
                    'error': str(e),
                    'error_type': 'ssrf_blocked',
                    'processing_time_seconds': processing_time,
                    'priority': priority
                }

            # Step 3: Create output folder
            output_folder = self._create_output_folder(url, request_id)
            logger.info(f"📂 Archive directory: {output_folder}")

            # Step 4: Create generators
            generators = self.generator_factory.create_generators(domain_config)
            logger.info(f"🔧 Initialized {len(generators)} archive generators")
            
            # Step 5: Run each generator
            all_artifacts = []
            overall_success = True
            error_messages = []
            
            for gen_config in domain_config.generators:
                generator = next((g for g in generators if g.__class__.__name__.lower().startswith(gen_config.name)), None)
                if not generator:
                    continue
                
                logger.info(f"📦 Running {gen_config.name} generator for {url}")
                try:
                    artifact_results = await generator.generate_archive(url, output_folder, gen_config.artifacts)
                    all_artifacts.extend(artifact_results)
                    
                    # Check for failures in requested artifacts
                    failed = [a for a in artifact_results if a.status == ArtifactStatus.FAILED]
                    if failed:
                        overall_success = False
                        for a in failed:
                            error_messages.append(f"{gen_config.name}: {a.name} failed - {a.error}")
                except Exception as e:
                    logger.error(f"❌ {gen_config.name} generator failed: {e}")
                    overall_success = False
                    error_messages.append(f"{gen_config.name} catastrophic failure: {e}")
            
            # Step 6: Create ArchiveResult
            processing_time = (datetime.now() - start_time).total_seconds()
            snapshot_id = os.path.basename(output_folder)
            
            if overall_success:
                archive_result = ArchiveResult.create_success(
                    archive_path=output_folder,
                    request_id=request_id,
                    url=url,
                    artifacts=all_artifacts,
                    processing_time_seconds=processing_time,
                    snapshot_id=snapshot_id
                )
            else:
                combined_error = "; ".join(error_messages)
                archive_result = ArchiveResult.create_failure(
                    archive_path=output_folder,
                    request_id=request_id,
                    url=url,
                    error_message=combined_error,
                    error_type="archive_generation_failed",
                    artifacts=all_artifacts,
                    processing_time_seconds=processing_time,
                    snapshot_id=snapshot_id
                )

            # Step 8: Final metadata generation
            metadata = self._generate_metadata(url, output_folder, start_time, all_artifacts, request_id)
            await self._save_metadata(metadata, output_folder)
            
            # Step 9: Store archive
            storage_result = await self._store_archive(
                archive_result.archive_path, url, domain_config, request_id
            )
            logger.info("💾 Archive stored successfully")
            
            result = {
                'success': archive_result.success,
                'request_id': request_id,
                'url': url,
                'archive_path': archive_result.archive_path,
                'snapshot_id': archive_result.snapshot_id,
                'storage_result': storage_result,
                'artifacts_created': archive_result.artifacts_created,
                'domain_config': {
                    'name': domain_config.name,
                    'webpage_types': domain_config.webpage_types,
                    'generators': [g.model_dump() for g in domain_config.generators]
                },
                'processing_time_seconds': processing_time,
                'priority': priority
            }
            if not archive_result.success:
                result['error'] = archive_result.error_message
                result['error_type'] = archive_result.error_type
            
            logger.info(f"🎉 Archive creation completed for request {request_id} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time_ts
            error_msg = str(e)
            logger.error(f"❌ Archive creation failed: {error_msg}", exc_info=True)
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
                    domain.lower().endswith("." + config_name) or
                    (domain_config.is_wildcard and domain.lower().endswith(config_name.replace("*", "")))):
                    
                    logger.debug(f"✅ Found matching domain config: {domain_config.name}")
                    return domain_config
            
            logger.debug(f"❌ No domain config found for: {domain}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing URL {url}: {e}")
            return None
    
    async def _validate_url_for_ssrf(self, url: str) -> None:
        """Check if URL points to a prohibited IP address or range (SSRF protection)."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                return

            # Resolve hostname via the event loop — non-blocking unlike socket.gethostbyname
            results = await asyncio.get_running_loop().getaddrinfo(hostname, None)
            ip_address = results[0][4][0]
            ip = ipaddress.ip_address(ip_address)

            # Block private/local IP ranges
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                raise ValueError(f"URL resolves to a prohibited private/local IP address: {ip_address}")

        except OSError:
            logger.warning(f"Could not resolve hostname: {urlparse(url).hostname}")
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error during SSRF validation: {e}")

    def _create_output_folder(self, url: str, request_id: str) -> str:
        """Create a structured archive output directory."""
        parsed = urlparse(url)
        domain = (parsed.hostname or parsed.netloc.split(':')[0]).replace(".", "_").replace("-", "_")
        path_part = parsed.path.strip("/").replace("/", "_").replace("-", "_")
        if not path_part:
            path_part = "home_page"
        
        safe_request_id = "".join(c for c in request_id if c.isalnum() or c in "-_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        output_folder = os.path.join(
            self.config.app.archive_directory,
            domain,
            path_part,
            f"req_{safe_request_id}_{timestamp}"
        )
        os.makedirs(output_folder, exist_ok=True)
        return output_folder

    def _generate_metadata(self, url: str, output_folder: str, start_time: datetime, artifacts: List[ArtifactResult], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate metadata.json for the archive."""
        end_time = datetime.now()
        files = []
        for file_path in Path(output_folder).iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'name': file_path.name,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        metadata = {
            'archive_info': {
                'url': url,
                'request_id': request_id,
                'created_at': start_time.isoformat(),
                'completed_at': end_time.isoformat(),
                'processing_time_seconds': (end_time - start_time).total_seconds(),
                'generator': 'ArchiveService_v2',
                'version': '2.0.0'
            },
            'artifacts_created': [a.name for a in artifacts if a.status == ArtifactStatus.SUCCESS],
            'failed_artifacts': [a.name for a in artifacts if a.status == ArtifactStatus.FAILED],
            'files': files
        }
        return metadata

    async def _save_metadata(self, metadata: Dict[str, Any], output_folder: str) -> None:
        """Save metadata to metadata.json."""
        meta_path = os.path.join(output_folder, "metadata.json")
        content = json.dumps(metadata, indent=2, ensure_ascii=False)
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(content)
    
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
                'artifacts': [a for g in domain_config.generators for a in g.artifacts],
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
