"""
Unit tests for snapshot detail API endpoint.

Tests the GET /api/snapshots/{snapshot_id} endpoint functionality.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import Snapshot
from app.storage import StorageError

# Mock storage for testing
class MockStorageService:
    """Mock storage service for testing."""
    
    def __init__(self):
        # Create test snapshot data
        self.test_snapshot = Snapshot(
            snapshot_id="req_test-request-1_20250904_061411",
            timestamp=datetime(2025, 9, 4, 6, 14, 11, tzinfo=timezone.utc),
            url="https://example.com",
            title="Example Domain",
            folder_path="/test/archives/example_com/home_page/req_test-request-1_20250904_061411",
            metadata={
                "status": 200,
                "content_type": "text/html",
                "content_length": 1256,
                "user_agent": "Mozilla/5.0",
                "capture_date": "2025-09-04T06:14:11Z"
            },
            available_artifacts=["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]
        )
    
    def get_snapshot_by_id(self, snapshot_id: str):
        """Mock snapshot lookup."""
        if snapshot_id == "req_test-request-1_20250904_061411":
            return self.test_snapshot
        elif snapshot_id == "nonexistent":
            return None
        elif snapshot_id == "storage_error":
            raise StorageError("Storage operation failed")
        else:
            return None


# Test client with mocked storage
@pytest.fixture
def client():
    """Test client with mocked storage service."""
    test_app = app
    test_app.state.storage_service = MockStorageService()
    return TestClient(test_app)


class TestSnapshotDetail:
    """Test cases for snapshot detail API endpoint."""
    
    def test_get_snapshot_detail_success(self, client):
        """Test successful snapshot detail retrieval."""
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify basic snapshot information
        assert data["snapshot_id"] == snapshot_id
        assert data["original_url"] == "https://example.com/"
        assert data["title"] == "Example Domain"
        assert data["timestamp"] == "2025-09-04T06:14:11+00:00"
        assert data["readable_timestamp"] == "2025-09-04 06:14:11 UTC"
        
        # Verify metadata
        assert data["metadata"]["status"] == 200
        assert data["metadata"]["content_type"] == "text/html"
        assert data["metadata"]["content_length"] == 1256
        
        # Verify computed fields
        assert data["artifact_count"] == 4
        assert data["status_code"] == 200
        assert data["content_type"] == "text/html"
        assert data["content_length"] == 1256
        assert data["has_replay_content"] == True  # Has WACZ
        
        # Verify artifact information structure
        artifacts = data["artifacts"]
        
        # Check available artifacts
        for artifact_type in ["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]:
            assert artifact_type in artifacts
            assert artifacts[artifact_type]["available"] == True
            assert artifacts[artifact_type]["download_url"] is not None
            assert f"snapshot_id={snapshot_id}" in artifacts[artifact_type]["download_url"]
            assert f"type={artifact_type}" in artifacts[artifact_type]["download_url"]
        
        # Check unavailable artifacts
        for artifact_type in ["archive.warc", "document.html"]:
            assert artifact_type in artifacts
            assert artifacts[artifact_type]["available"] == False
            assert artifacts[artifact_type]["download_url"] is None
    
    def test_get_snapshot_detail_not_found(self, client):
        """Test 404 response for non-existent snapshot."""
        response = client.get("/api/snapshots/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_get_snapshot_detail_storage_error(self, client):
        """Test 500 response for storage errors."""
        response = client.get("/api/snapshots/storage_error")
        
        assert response.status_code == 500
        data = response.json()
        assert "storage operation failed" in data["message"].lower()
    
    def test_get_snapshot_detail_invalid_snapshot_id_format(self, client):
        """Test handling of invalid snapshot ID format."""
        # This should still return 404, not a validation error
        response = client.get("/api/snapshots/invalid-format")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_artifact_download_urls_format(self, client):
        """Test that artifact download URLs are correctly formatted."""
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify download URL format for available artifacts
        wacz_artifact = data["artifacts"]["archive.wacz"]
        assert wacz_artifact["available"] == True
        assert wacz_artifact["download_url"] == f"http://testserver/api/artifacts/serve?snapshot_id={snapshot_id}&type=archive.wacz"
        
        # Verify that unavailable artifacts have no download URL
        warc_artifact = data["artifacts"]["archive.warc"]
        assert warc_artifact["available"] == False
        assert warc_artifact["download_url"] is None
    
    def test_response_schema_completeness(self, client):
        """Test that response includes all expected fields."""
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        required_fields = [
            "snapshot_id", "timestamp", "readable_timestamp", "original_url",
            "artifacts", "metadata", "artifact_count", "has_replay_content"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Optional fields should be present with correct types
        assert isinstance(data.get("title"), (str, type(None)))
        assert isinstance(data.get("status_code"), (int, type(None)))
        assert isinstance(data.get("content_type"), (str, type(None)))
        assert isinstance(data.get("content_length"), (int, type(None)))
        
        # Artifacts should include all expected types
        expected_artifact_types = ["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html", "archive.warc", "document.html"]
        for artifact_type in expected_artifact_types:
            assert artifact_type in data["artifacts"]
            artifact_info = data["artifacts"][artifact_type]
            assert "available" in artifact_info
            assert "size_bytes" in artifact_info
            assert "download_url" in artifact_info
    
    def test_metadata_passthrough(self, client):
        """Test that metadata from storage is correctly passed through."""
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify metadata is complete and includes custom fields
        metadata = data["metadata"]
        assert metadata["status"] == 200
        assert metadata["content_type"] == "text/html"
        assert metadata["content_length"] == 1256
        assert metadata["user_agent"] == "Mozilla/5.0"
        assert metadata["capture_date"] == "2025-09-04T06:14:11Z"
    
    def test_has_replay_content_logic(self, client):
        """Test replay content availability detection."""
        # Test with WACZ available (should be True)
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["has_replay_content"] == True
        
        # Mock a snapshot with only WARC (should also be True)
        with patch.object(client.app.state.storage_service, 'get_snapshot_by_id') as mock_get:
            warc_snapshot = Snapshot(
                snapshot_id="req_test-warc_20250904_061411",
                timestamp=datetime(2025, 9, 4, 6, 14, 11, tzinfo=timezone.utc),
                url="https://example.com",
                available_artifacts=["archive.warc", "metadata.json"]
            )
            mock_get.return_value = warc_snapshot
            
            response = client.get("/api/snapshots/req_test-warc_20250904_061411")
            assert response.status_code == 200
            data = response.json()
            assert data["has_replay_content"] == True
        
        # Mock a snapshot with neither WACZ nor WARC (should be False)
        with patch.object(client.app.state.storage_service, 'get_snapshot_by_id') as mock_get:
            no_replay_snapshot = Snapshot(
                snapshot_id="req_test-noreplay_20250904_061411",
                timestamp=datetime(2025, 9, 4, 6, 14, 11, tzinfo=timezone.utc),
                url="https://example.com",
                available_artifacts=["metadata.json", "screenshot.png"]
            )
            mock_get.return_value = no_replay_snapshot
            
            response = client.get("/api/snapshots/req_test-noreplay_20250904_061411")
            assert response.status_code == 200
            data = response.json()
            assert data["has_replay_content"] == False
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    def test_file_size_calculation(self, mock_stat, mock_exists, client):
        """Test file size calculation for artifacts."""
        # Mock file exists and stat
        mock_exists.return_value = True
        mock_stat_result = Mock()
        mock_stat_result.st_size = 1024
        mock_stat.return_value = mock_stat_result
        
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that file sizes are calculated for available artifacts
        wacz_artifact = data["artifacts"]["archive.wacz"]
        assert wacz_artifact["available"] == True
        assert wacz_artifact["size_bytes"] == 1024
    
    @patch('pathlib.Path.exists')
    def test_file_size_unavailable_handling(self, mock_exists, client):
        """Test handling when file size calculation fails."""
        # Mock file doesn't exist
        mock_exists.return_value = False
        
        snapshot_id = "req_test-request-1_20250904_061411"
        response = client.get(f"/api/snapshots/{snapshot_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that missing files still show as available (from metadata) but no size
        wacz_artifact = data["artifacts"]["archive.wacz"]
        assert wacz_artifact["available"] == True
        assert wacz_artifact["size_bytes"] is None
    
    def test_empty_metadata_handling(self, client):
        """Test handling of snapshots with minimal metadata."""
        with patch.object(client.app.state.storage_service, 'get_snapshot_by_id') as mock_get:
            minimal_snapshot = Snapshot(
                snapshot_id="req_test-minimal_20250904_061411",
                timestamp=datetime(2025, 9, 4, 6, 14, 11, tzinfo=timezone.utc),
                url="https://example.com",
                title=None,  # No title
                metadata={},  # Empty metadata
                available_artifacts=[]  # No artifacts
            )
            mock_get.return_value = minimal_snapshot
            
            response = client.get("/api/snapshots/req_test-minimal_20250904_061411")
            assert response.status_code == 200
            data = response.json()
            
            # Verify handling of missing data
            assert data["title"] is None
            assert data["status_code"] is None
            assert data["content_type"] is None
            assert data["content_length"] is None
            assert data["artifact_count"] == 0
            assert data["has_replay_content"] == False
            assert data["metadata"] == {}
            
            # All artifacts should be unavailable
            for artifact_info in data["artifacts"].values():
                assert artifact_info["available"] == False
                assert artifact_info["download_url"] is None


if __name__ == "__main__":
    pytest.main([__file__])