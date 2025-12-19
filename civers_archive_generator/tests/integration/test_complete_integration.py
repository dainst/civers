# tests/Integration_tests/test_phase3_integration.py
import pytest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path

from configs.loaders import YamlFileConfigLoader
from archive_services.archive_service import ArchiveService
from transport_services import KafkaTransportService


class TestComponentIntegration:
    """Integration tests for component architecture - testing component interactions.
    
    Note: These are NOT end-to-end tests. They test integration between 2-3 components
    but do not test the complete application workflow or main_app initialization.
    """
    
    @pytest.fixture
    def temp_archive_dir(self):
        """Create a temporary directory for test archives."""
        temp_dir = tempfile.mkdtemp(prefix="test_archives_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def integration_config(self, temp_archive_dir):
        """Create integration test config with temp directory."""
        config = YamlFileConfigLoader().load()
        # Update paths to use temp directory
        config.app.archive_directory = temp_archive_dir
        if hasattr(config.app, 'storage') and hasattr(config.app.storage, 'backends'):
            config.app.storage.backends['local_file']['base_path'] = temp_archive_dir
        return config
    
    @pytest.mark.asyncio
    async def test_configuration_loading_integration(self):
        """Test that configuration loads correctly and all components can access it."""
        # Test real configuration loading using YamlFileConfigLoader
        config = YamlFileConfigLoader().load()
        
        # Test configuration structure
        assert config.app.name == "archive_generator"
        assert config.app.version == "1.0.0"
        
        # Test transport configuration exists
        assert config.app.transport is not None
        assert config.app.transport.kafka is not None
        
        # Test storage configuration exists
        assert config.app.storage is not None
        assert len(config.app.storage.get_enabled_backends()) > 0
        
        # Test domains configuration
        assert len(config.domains) > 0
    
    @pytest.mark.asyncio
    async def test_archive_service_integration(self, integration_config, temp_archive_dir):
        """Test archive service integration with real components."""
        # Test real archive service initialization
        archive_service = ArchiveService(integration_config)
        
        # Test domain configuration integration
        supported_domains = archive_service.get_supported_domains()
        assert len(supported_domains) >= 2  # At least test domains
        assert "arachne.dainst.org" in supported_domains
        assert "field.dainst.org" in supported_domains
        
        # Test domain-specific configuration retrieval
        arachne_config = archive_service.get_domain_config("arachne.dainst.org")
        assert arachne_config is not None
        assert arachne_config.name == "arachne.dainst.org"
        assert "warc" in arachne_config.artifacts
        assert arachne_config.webpage_types == "dynamic"
        
        # Test invalid domain handling - should raise ValueError with new interface
        with pytest.raises(ValueError, match="Domain 'nonexistent.domain.com' is not supported"):
            archive_service.get_domain_config("nonexistent.domain.com")
        
        # Test URL validation
        validation_result = archive_service.validate_url("https://arachne.dainst.org/test")
        assert validation_result['valid'] is True
        assert validation_result['domain_config'] is not None
        
        # Test invalid URL validation
        invalid_validation = archive_service.validate_url("https://unsupported.domain.com/test")
        assert invalid_validation['valid'] is False
    
    @pytest.mark.asyncio 
    async def test_component_integration_without_kafka(self, integration_config, temp_archive_dir):
        """Test integration between main components without external Kafka dependency."""
        # Test that components can be created and interact properly
        archive_service = ArchiveService(integration_config)
        
        # Test service initialization
        assert archive_service.config is not None
        assert len(archive_service.get_supported_domains()) > 0
        
        # Test that storage directories are created
        storage_path = Path(temp_archive_dir)
        assert storage_path.exists()
        
        # Test domain validation
        valid_domains = ["arachne.dainst.org", "field.dainst.org"]
        for domain in valid_domains:
            domain_config = archive_service.get_domain_config(domain)
            assert domain_config is not None
            assert domain_config.name == domain
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, integration_config):
        """Test error handling across integrated components."""
        archive_service = ArchiveService(integration_config)
        
        # Test invalid domain handling - should raise ValueError with new interface
        with pytest.raises(ValueError, match="Domain 'definitely.not.a.valid.domain.com' is not supported"):
            archive_service.get_domain_config("definitely.not.a.valid.domain.com")
        
        # Test empty domain name - should raise ValueError
        with pytest.raises(ValueError, match="Domain '' is not supported"):
            archive_service.get_domain_config("")
        
        # Test None domain name - should raise ValueError
        with pytest.raises(ValueError, match="Domain 'None' is not supported"):
            archive_service.get_domain_config(None)
