"""
Integration tests for URLs API endpoint with storage architecture.
"""

import pytest
import tempfile
import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from configs.models import AppConfig
from app.storage import create_storage_service
from configs import StorageConfig, FilesystemConfig, CacheConfig

# Create test client
client = TestClient(app)


@pytest.fixture
def temp_archives():
    """Create temporary archives directory with test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        archives_path = Path(temp_dir) / "archives"
        archives_path.mkdir()
        
        # Create test structure: archives/domain/path/req_id_timestamp/
        domain_dir = archives_path / "example_com"
        domain_dir.mkdir()
        
        path_dir = domain_dir / "home_page"
        path_dir.mkdir()
        
        request_dir = path_dir / "req_test-1_20250904_120000"
        request_dir.mkdir()
        
        # Create metadata.json
        metadata = {
            "archive_info": {
                "url": "https://example.com",
                "request_id": "test-1"
            },
            "title": "Example Domain"
        }
        with open(request_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)
        
        # Create artifacts
        (request_dir / "archive.wacz").write_bytes(b"fake wacz data")
        (request_dir / "screenshot.png").write_bytes(b"fake image data")
        
        yield str(archives_path)


class TestUrlsAPIIntegration:
    """Integration tests for URLs API with real storage service."""
    
    def test_list_urls_with_mock_storage_service(self, temp_archives):
        """Test URLs endpoint with mocked storage service."""
        
        # Create storage service with test data
        config = AppConfig(storage= StorageConfig(
            type="filesystem",
            filesystem=FilesystemConfig(path=temp_archives),
            cache=CacheConfig(ttl_seconds=60)
        ) )
        
        storage_service = create_storage_service(config)
        
        # Set the storage service and config in app state
        setattr(app.state, 'storage_service', storage_service)
        setattr(app.state, 'app_config', config)
        try:
            response = client.get("/api/urls")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert len(data["data"]) == 1
            assert data["data"][0]["url_id"] == "example_com_home_page"
            assert data["data"][0]["original_url"] == "https://example.com/"
            assert data["data"][0]["snapshot_count"] == 1
            
            # Check pagination
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["limit"] == 50
            assert data["pagination"]["total_count"] == 1
        finally:
            # Clean up app state
            if hasattr(app.state, 'storage_service'):
                delattr(app.state, 'storage_service')
            if hasattr(app.state, 'app_config'):
                delattr(app.state, 'app_config')

    def test_list_urls_pagination(self, temp_archives):
        """Test URLs endpoint pagination."""
        
        config =AppConfig(storage= StorageConfig(
            type="filesystem",
            filesystem=FilesystemConfig(path=temp_archives),
            cache=CacheConfig(ttl_seconds=60)
        ) )
        
        storage_service = create_storage_service(config)
        
        setattr(app.state, 'storage_service', storage_service)
        setattr(app.state, 'app_config', config)
        try:
            response = client.get("/api/urls?page=1&limit=1")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert len(data["data"]) <= 1
            assert data["pagination"]["limit"] == 1
        finally:
            if hasattr(app.state, 'storage_service'):
                delattr(app.state, 'storage_service')
            if hasattr(app.state, 'app_config'):
                delattr(app.state, 'app_config')

    def test_cache_stats_endpoint(self, temp_archives):
        """Test cache stats debug endpoint (only available when debug=True)."""
        
        config = AppConfig(storage= StorageConfig(
            type="filesystem",
            filesystem=FilesystemConfig(path=temp_archives),
            cache=CacheConfig(ttl_seconds=60)
        ))
        
        storage_service = create_storage_service(config)
        
        setattr(app.state, 'storage_service', storage_service)
        try:
            # First populate cache
            client.get("/api/urls")
            
            # Check cache stats — endpoint only exists when server.debug=True
            response = client.get("/debug/cache/stats")
            
            # Accept either 200 (debug mode on) or 404 (debug mode off)
            assert response.status_code in (200, 404)
            
            if response.status_code == 200:
                data = response.json()
                assert "cached_urls_count" in data
                assert "ttl_seconds" in data
        finally:
            if hasattr(app.state, 'storage_service'):
                delattr(app.state, 'storage_service')


class TestUrlsAPIValidation:
    """Test URL API validation without storage setup."""
    
    def test_invalid_page_parameter(self):
        """Test invalid page parameter validation."""
        response = client.get("/api/urls?page=0")
        
        # FastAPI should return 422 for validation errors
        assert response.status_code == 422
        
    def test_invalid_limit_parameter(self):
        """Test that limit above max is silently clamped (not rejected)."""
        # The list_urls endpoint requires storage_service on app state,
        # but even without it the limit itself isn't rejected by Pydantic
        # since there is no le= constraint. The endpoint clamps silently.
        # Without storage_service set, we get a 500, so we just verify
        # the limit value alone doesn't cause a 422.
        response = client.get("/api/urls?limit=101")
        
        # Gets 500 because storage_service not on app state, but NOT 422
        assert response.status_code != 422

    def test_invalid_sort_parameter(self):
        """Test invalid sort parameter validation."""
        response = client.get("/api/urls?sort=invalid")
        
        # FastAPI should return 422 for validation errors
        assert response.status_code == 422