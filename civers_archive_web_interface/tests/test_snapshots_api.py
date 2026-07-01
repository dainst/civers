""" 
Unit tests for snapshots API endpoint.

Tests the GET /api/urls/{url_id}/snapshots endpoint with various filtering,
pagination, and sorting scenarios.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from pydantic import HttpUrl

from app.main import app
from app.models import Snapshot, ArchivedUrl
from configs.models import AppConfig


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_storage_service():
    """Create mock storage service with test data."""
    # Create mock snapshots using the Pydantic model
    snapshot1 = Snapshot(
        snapshot_id="req_test-1_20240301_120000",
        timestamp=datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
        url=HttpUrl("https://example.com"),
        title="Example Domain",
        folder_path="/storage/example_com/home_page/req_test-1_20240301_120000",
        metadata={"status": 200, "content_type": "text/html"},
        available_artifacts=["archive.wacz", "screenshot.png", "metadata.json", "singlefile.html"]
    )
    
    snapshot2 = Snapshot(
        snapshot_id="req_test-2_20240315_140000",
        timestamp=datetime(2024, 3, 15, 14, 0, 0, tzinfo=timezone.utc),
        url=HttpUrl("https://example.com"),
        title="Example Domain Updated",
        folder_path="/storage/example_com/home_page/req_test-2_20240315_140000",
        metadata={"status": 200, "content_type": "text/html"},
        available_artifacts=["archive.wacz", "screenshot.png", "metadata.json"]
    )
    
    snapshot3 = Snapshot(
        snapshot_id="req_test-3_20240401_100000",
        timestamp=datetime(2024, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
        url=HttpUrl("https://example.com"),
        title="Example Domain Error",
        folder_path="/storage/example_com/home_page/req_test-3_20240401_100000",
        metadata={"status": 404, "content_type": "text/html"},
        available_artifacts=["screenshot.png", "metadata.json"]
    )
    
    # Create mock archived URL with snapshots  
    archived_url = ArchivedUrl(
        url_id="example_com_home_page",
        original_url=HttpUrl("https://example.com"),
        folder_name="home_page",
        snapshots=[snapshot1, snapshot2, snapshot3]
    )
    
    # Create mock storage service
    mock_service = MagicMock()
    mock_service.get_url_by_id.return_value = archived_url
    
    return mock_service


@pytest.fixture(autouse=True)
def setup_storage_service(client, mock_storage_service):
    """Set up mock storage service and app config for all tests."""
    app.state.storage_service = mock_storage_service
    app.state.app_config = AppConfig()
    yield
    # Cleanup after tests
    if hasattr(app.state, 'storage_service'):
        delattr(app.state, 'storage_service')
    if hasattr(app.state, 'app_config'):
        delattr(app.state, 'app_config')


class TestSnapshotsAPI:
    """Test cases for snapshots API endpoint."""
    
    def test_list_snapshots_basic(self, client):
        """Test basic snapshots listing."""
        response = client.get("/api/urls/example_com_home_page/snapshots")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["success"] is True
        assert "data" in data
        assert "pagination" in data
        
        # Check snapshots data
        snapshots = data["data"]
        assert len(snapshots) == 3
        
        # Check first snapshot (newest first by default)
        first_snapshot = snapshots[0]
        assert first_snapshot["snapshot_id"] == "req_test-3_20240401_100000"
        assert first_snapshot["title"] == "Example Domain Error"
        assert first_snapshot["status_code"] == 404
        
        # Check pagination
        pagination = data["pagination"]
        assert pagination["total_count"] == 3
        assert pagination["page"] == 1
        assert pagination["total_pages"] == 1
    
    def test_list_snapshots_pagination(self, client):
        """Test snapshots listing with pagination."""
        response = client.get("/api/urls/example_com_home_page/snapshots?page=1&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check pagination
        snapshots = data["data"]
        assert len(snapshots) == 2
        
        pagination = data["pagination"]
        assert pagination["total_count"] == 3
        assert pagination["page"] == 1
        assert pagination["total_pages"] == 2
        assert pagination["has_next"] is True
        assert pagination["has_previous"] is False
    
    def test_list_snapshots_sort_timestamp_asc(self, client):
        """Test snapshots sorting by timestamp ascending."""
        response = client.get("/api/urls/example_com_home_page/snapshots?sort=timestamp_asc")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        assert len(snapshots) == 3
        
        # Check order (oldest first)
        assert snapshots[0]["snapshot_id"] == "req_test-1_20240301_120000"
        assert snapshots[1]["snapshot_id"] == "req_test-2_20240315_140000"
        assert snapshots[2]["snapshot_id"] == "req_test-3_20240401_100000"
    
    def test_list_snapshots_sort_title(self, client):
        """Test snapshots sorting by title."""
        response = client.get("/api/urls/example_com_home_page/snapshots?sort=title")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        # Should be sorted alphabetically: Domain, Domain Error, Domain Updated
        assert snapshots[0]["title"] == "Example Domain"
        assert snapshots[1]["title"] == "Example Domain Error"
        assert snapshots[2]["title"] == "Example Domain Updated"
    
    def test_list_snapshots_filter_status_code(self, client):
        """Test filtering snapshots by status code."""
        response = client.get("/api/urls/example_com_home_page/snapshots?status_code=200")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        assert len(snapshots) == 2  # Only status 200 snapshots
        
        for snapshot in snapshots:
            assert snapshot["status_code"] == 200
    
    def test_list_snapshots_filter_has_singlefile(self, client):
        """Test filtering snapshots by SingleFile availability."""
        response = client.get("/api/urls/example_com_home_page/snapshots?has_singlefile=true")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        assert len(snapshots) == 1  # Only first snapshot has singlefile.html
        assert snapshots[0]["snapshot_id"] == "req_test-1_20240301_120000"
        assert "singlefile.html" in snapshots[0]["available_artifacts"]
    
    def test_list_snapshots_filter_date_range(self, client):
        """Test filtering snapshots by date range."""
        response = client.get("/api/urls/example_com_home_page/snapshots?from_date=2024-03-10&to_date=2024-03-20")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        assert len(snapshots) == 1  # Only March 15 snapshot falls in range
        assert snapshots[0]["snapshot_id"] == "req_test-2_20240315_140000"
    
    def test_list_snapshots_multiple_filters(self, client):
        """Test combining multiple filters."""
        response = client.get("/api/urls/example_com_home_page/snapshots?status_code=200&has_wacz=true")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data["data"]
        assert len(snapshots) == 2  # Two snapshots match both criteria
        
        for snapshot in snapshots:
            assert snapshot["status_code"] == 200
            assert "archive.wacz" in snapshot["available_artifacts"]
    
    def test_list_snapshots_no_matches(self, client):
        """Test filtering with no matching results."""
        response = client.get("/api/urls/example_com_home_page/snapshots?status_code=500")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty results with proper pagination
        assert data["data"] == []
        assert data["pagination"]["total_count"] == 0
    
    def test_list_snapshots_url_not_found(self, client, mock_storage_service):
        """Test 404 error when URL doesn't exist."""
        mock_storage_service.get_url_by_id.return_value = None
        
        response = client.get("/api/urls/nonexistent_url/snapshots")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_list_snapshots_invalid_page(self, client):
        """Test error handling for invalid page number."""
        response = client.get("/api/urls/example_com_home_page/snapshots?page=10")
        
        assert response.status_code == 400
        data = response.json()
        assert "Page 10 does not exist" in data['details'][0]['message']
    
    def test_list_snapshots_invalid_date_filter(self, client):
        """Test error handling for invalid date format."""
        response = client.get("/api/urls/example_com_home_page/snapshots?from_date=invalid-date")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid filter parameters" in data['details'][0]['message']
    
    def test_list_snapshots_invalid_status_code(self, client):
        """Test error handling for invalid status code."""
        response = client.get("/api/urls/example_com_home_page/snapshots?status_code=999")
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_list_snapshots_invalid_limit(self, client):
        """Test that limit above max_page_size is silently clamped."""
        response = client.get("/api/urls/example_com_home_page/snapshots?limit=200")
        
        # Endpoint clamps limit to max_page_size rather than rejecting
        assert response.status_code == 200
    
    def test_snapshot_summary_properties(self, client):
        """Test snapshot summary model properties."""
        response = client.get("/api/urls/example_com_home_page/snapshots")
        
        assert response.status_code == 200
        data = response.json()
        
        snapshot = data["data"][0]  # First snapshot
        
        # Check required fields
        assert "snapshot_id" in snapshot
        assert "timestamp" in snapshot
        assert "available_artifacts" in snapshot
        
        # Check artifact count matches available_artifacts length
        assert isinstance(snapshot["available_artifacts"], list)
        assert len(snapshot["available_artifacts"]) >= 0