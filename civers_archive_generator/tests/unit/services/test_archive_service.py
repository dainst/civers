# tests/unit/services/test_archive_service.py
import pytest
from unittest.mock import Mock, patch, AsyncMock

from configs.models import DomainConfig
from archive_services.archive_service import ArchiveService
from archive_generators.archive_result import ArchiveResult, ArtifactResult, ArtifactStatus


@pytest.fixture
def archive_service(sample_config):
    """Create an ArchiveService instance for testing."""
    return ArchiveService(sample_config)


@pytest.mark.unit
class TestArchiveService:
    """Test suite for ArchiveService core business logic."""
    
    def test_init(self, sample_config):
        """Test ArchiveService initialization."""
        service = ArchiveService(sample_config)
        
        assert service.config == sample_config
        assert service.config.domains is not None
        assert len(service.config.domains) == 2
    
    def test_get_supported_domains(self, archive_service):
        """Test getting supported domains list."""
        domains = archive_service.get_supported_domains()
        
        assert isinstance(domains, list)
        assert "example.com" in domains
        assert "static-site.org" in domains
        assert len(domains) == 2
    
    def test_get_domain_config_found(self, archive_service):
        """Test getting domain configuration when it exists."""
        domain_config = archive_service.get_domain_config("example.com")
        
        assert domain_config is not None
        assert domain_config.name == "example.com"
        assert domain_config.webpage_types == "dynamic"
        assert len(domain_config.generators) > 0
        assert domain_config.generators[0].name == "scoop"
    
    def test_get_domain_config_not_found(self, archive_service):
        """Test getting domain configuration when it doesn't exist."""
        with pytest.raises(ValueError, match="Domain 'unknown.com' is not supported"):
            archive_service.get_domain_config("unknown.com")
    
    def test_find_domain_config_exact_match(self, archive_service):
        """Test finding domain config with exact domain match."""
        domain_config = archive_service._find_domain_config("https://example.com/page")
        
        assert domain_config is not None
        assert domain_config.name == "example.com"
    
    def test_find_domain_config_partial_match(self, archive_service):
        """Test finding domain config with partial domain match."""
        domain_config = archive_service._find_domain_config("https://www.example.com/page")
        
        assert domain_config is not None
        assert domain_config.name == "example.com"
    
    def test_find_domain_config_not_found(self, archive_service):
        """Test finding domain config when no match exists."""
        domain_config = archive_service._find_domain_config("https://unknown.com/page")
        
        assert domain_config is None
    
    def test_find_domain_config_invalid_url(self, archive_service):
        """Test finding domain config with invalid URL."""
        domain_config = archive_service._find_domain_config("not-a-valid-url")
        
        assert domain_config is None
    
    def test_validate_url_valid(self, archive_service):
        """Test URL validation with valid URL."""
        result = archive_service.validate_url("https://example.com/test")
        
        assert result['valid'] is True
        assert result['url'] == "https://example.com/test"
        assert result['domain'] == "example.com"
        assert 'domain_config' in result
        assert result['domain_config'].name == "example.com"
    
    def test_validate_url_invalid_format(self, archive_service):
        """Test URL validation with invalid format."""
        result = archive_service.validate_url("not-a-url")
        
        assert result['valid'] is False
        assert 'Invalid URL format' in result['reason']
    
    def test_validate_url_no_domain_config(self, archive_service):
        """Test URL validation with no matching domain config."""
        result = archive_service.validate_url("https://unknown.com/test")
        
        assert result['valid'] is False
        assert 'No domain configuration found' in result['reason']
        assert result['domain'] == "unknown.com"
        assert 'supported_domains' in result
    
    @patch('archive_services.archive_service.ArchiveGeneratorFactory')
    def test_create_generators(self, mock_factory_class, archive_service):
        """Test creating generators via factory."""
        # Setup mock factory
        mock_factory = mock_factory_class.return_value
        mock_generators = [Mock(), Mock()]
        mock_factory.create_generators.return_value = mock_generators
        
        # Replace the factory in the service
        archive_service.generator_factory = mock_factory
        
        domain_config = DomainConfig(
            name="test.com",
            generators=[{"name": "scoop", "artifacts": ["warc"]}],
            webpage_types="dynamic"
        )
        
        generators = archive_service.generator_factory.create_generators(domain_config)
        
        mock_factory.create_generators.assert_called_once_with(domain_config)
        assert generators is mock_generators
    
    @pytest.mark.asyncio
    async def test_store_archive_success(self, archive_service):
        """Test successful archive storage."""
        domain_config = DomainConfig(
            name="test.com",
            generators=[{"name": "scoop", "artifacts": ["warc", "screenshot"]}],
            webpage_types="dynamic"
        )
        
        # ArtifactResults describing the files produced
        artifact_results = [
            ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/test.warc", 100),
            ArtifactResult("screenshot", ArtifactStatus.SUCCESS, "/tmp/screenshot.png", 50)
        ]
        
        archive_result = ArchiveResult.create_success(
            archive_path="/tmp/test.warc",
            url="https://test.com/page",
            request_id="test-request-id",
            artifacts=artifact_results,
            processing_time_seconds=1.0
        )
        
        result = await archive_service._store_archive(
            archive_result.archive_path,
            archive_result.url,
            domain_config,
            archive_result.request_id
        )
        
        assert 'storage_id' in result
        assert result['archive_path'] == "/tmp/test.warc"
        assert 'warc' in result['artifacts']
        assert 'screenshot' in result['artifacts']
        assert result['storage_backend'] == 'local_file'
        assert 'stored_at' in result
        assert 'files' in result
        assert 'total_size' in result
    
    @pytest.mark.asyncio
    async def test_create_archive_success(self, archive_service):
        """Test successful archive creation end-to-end."""
        url = "https://example.com/test-page"
        request_id = "test-req-123"
        priority = 1
        
        # Mock generator to return ArtifactResult
        mock_generator = AsyncMock()
        mock_generator.__class__.__name__ = "ScoopGenerator"
        mock_generator.generate_archive.return_value = [
            ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/test_archive.warc", 100),
            ArtifactResult("screenshot", ArtifactStatus.SUCCESS, "/tmp/screenshot.png", 50)
        ]
        
        archive_service.generator_factory = Mock()
        archive_service.generator_factory.create_generators.return_value = [mock_generator]
        
        # Also mock output folder creation, SSRF and metadata saving
        with patch('os.makedirs'), patch('archive_services.archive_service.urlparse'), \
             patch.object(archive_service, '_validate_url_for_ssrf'), \
             patch.object(archive_service, '_generate_metadata'), \
             patch.object(archive_service, '_save_metadata'), \
             patch.object(archive_service, '_store_archive', return_value={'storage_id': '123'}):
            result = await archive_service.create_archive(url, request_id, priority)
        
        # Verify result structure
        assert result['success'] is True
        assert result['request_id'] == request_id
        assert result['url'] == url
        assert 'archive_path' in result
        assert 'processing_time_seconds' in result
        
        # Verify domain config info
        assert result['domain_config']['name'] == "example.com"
        
        # Verify generator was called
        mock_generator.generate_archive.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_archive_no_domain_config(self, archive_service):
        """Test archive creation when no domain config is found."""
        url = "https://unknown-domain.com/test-page"
        request_id = "test-req-456"
        
        result = await archive_service.create_archive(url, request_id)
        
        assert result['success'] is False
        assert result['request_id'] == request_id
        assert result['url'] == url
        assert 'No domain configuration found' in result['error']
        assert result['error_type'] == 'configuration_not_found'
    
    @pytest.mark.asyncio
    async def test_create_archive_generator_failure(self, archive_service):
        """Test archive creation when generator execution fails."""
        url = "https://example.com/test-page"
        request_id = "test-req-789"
        
        mock_generator = AsyncMock()
        mock_generator.__class__.__name__ = "ScoopGenerator"
        mock_generator.generate_archive.side_effect = Exception("Scoop capture failed")
        
        archive_service.generator_factory = Mock()
        archive_service.generator_factory.create_generators.return_value = [mock_generator]
        
        with patch('os.makedirs'), \
             patch.object(archive_service, '_validate_url_for_ssrf'), \
             patch.object(archive_service, '_generate_metadata'), \
             patch.object(archive_service, '_save_metadata'), \
             patch.object(archive_service, '_store_archive', return_value={}):
            result = await archive_service.create_archive(url, request_id)
        
        assert result['success'] is False
        assert result['request_id'] == request_id
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_create_archive_with_priority(self, archive_service):
        """Test archive creation with custom priority."""
        url = "https://example.com/test-page"
        request_id = "test-req-priority"
        priority = 5
        
        mock_generator = AsyncMock()
        mock_generator.__class__.__name__ = "ScoopGenerator"
        mock_generator.generate_archive.return_value = []
        
        archive_service.generator_factory = Mock()
        archive_service.generator_factory.create_generators.return_value = [mock_generator]
        
        with patch('os.makedirs'), \
             patch.object(archive_service, '_validate_url_for_ssrf'), \
             patch.object(archive_service, '_generate_metadata'), \
             patch.object(archive_service, '_save_metadata'), \
             patch.object(archive_service, '_store_archive', return_value={}):
             result = await archive_service.create_archive(url, request_id, priority)
        
        assert result['success'] is True
        assert result['priority'] == priority


class TestArchiveServiceIntegration:
    """Integration tests for ArchiveService with real components."""
    
    @pytest.mark.asyncio
    async def test_create_archive_with_real_config(self, sample_config):
        """Test archive creation with real configuration structure."""
        service = ArchiveService(sample_config)
        
        # Mock generator to return ArtifactResult
        mock_generator = AsyncMock()
        mock_generator.__class__.__name__ = "ScoopGenerator"
        mock_generator.generate_archive.return_value = [
            ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/integration_test.warc", 100)
        ]
        
        service.generator_factory = Mock()
        service.generator_factory.create_generators.return_value = [mock_generator]
        
        with patch('os.makedirs'), patch.object(service, '_validate_url_for_ssrf'), \
             patch.object(service, '_generate_metadata'), \
             patch.object(service, '_save_metadata'), \
             patch.object(service, '_store_archive', return_value={'storage_id': '123'}):
            result = await service.create_archive(
                "https://example.com/integration-test", 
                "integration-test-123"
            )
        
        assert result['success'] is True
        assert result['domain_config']['name'] == "example.com"
        assert isinstance(result['processing_time_seconds'], float)
        assert result['processing_time_seconds'] > 0
    
    def test_domain_matching_various_formats(self, archive_service):
        """Test domain matching with various URL formats."""
        test_cases = [
            ("https://example.com", "example.com"),
            ("https://www.example.com/path", "example.com"),
            ("http://example.com:8080/path?query=1", "example.com"),
            ("https://subdomain.example.com", "example.com"),
        ]
        
        for url, expected_domain in test_cases:
            domain_config = archive_service._find_domain_config(url)
            assert domain_config is not None, f"Failed to find config for {url}"
            assert domain_config.name == expected_domain
