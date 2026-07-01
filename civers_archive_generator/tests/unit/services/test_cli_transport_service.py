import pytest
from unittest.mock import Mock, AsyncMock
from transport_services import CliTransportService
from configs.models import ConfigDataModel

@pytest.mark.unit
class TestCliTransportService:
    """Unit tests for the CliTransportService."""

    def test_initialization(self):
        """Test that CliTransportService initializes correctly."""
        mock_config = Mock(spec=ConfigDataModel)
        mock_archive_service = Mock()
        args = ["--url", "https://example.com", "--request-id", "test-123", "--priority", "2"]
        
        service = CliTransportService(mock_config, mock_archive_service, args=args)
        
        assert service.config == mock_config
        assert service.archive_service == mock_archive_service
        assert service.args == args
        assert service.running is False

    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test that start() successfully calls archive service and processes the URL."""
        mock_config = Mock(spec=ConfigDataModel)
        mock_archive_service = AsyncMock()
        mock_archive_service.create_archive.return_value = {
            "success": True,
            "archive_path": "/tmp/archive.wacz",
            "artifacts_created": ["warc"]
        }
        
        args = ["--url", "https://example.com", "--request-id", "test-123", "--priority", "2"]
        service = CliTransportService(mock_config, mock_archive_service, args=args)
        
        await service.start()
        
        mock_archive_service.create_archive.assert_called_once_with("https://example.com", "test-123", 2)
        assert service.running is False

    @pytest.mark.asyncio
    async def test_start_failure_exits(self):
        """Test that start() raises RuntimeError when archiving fails."""
        mock_config = Mock(spec=ConfigDataModel)
        mock_archive_service = AsyncMock()
        mock_archive_service.create_archive.return_value = {
            "success": False,
            "error": "Failed to crawl"
        }
        
        args = ["--url", "https://example.com"]
        service = CliTransportService(mock_config, mock_archive_service, args=args)
        
        with pytest.raises(RuntimeError) as excinfo:
            await service.start()
            
        assert "Archiving failed" in str(excinfo.value)
        mock_archive_service.create_archive.assert_called_once()
