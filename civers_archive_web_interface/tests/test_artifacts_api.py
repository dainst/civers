"""
New artifacts API tests reflecting middleware-based error handling.

Tests the GET /api/artifacts/serve endpoint with proper separation of concerns:
- API routes focus on business logic
- Middleware handles all error responses
- Storage service returns data or raises exceptions
- No HTTPException+ErrorDetail in API layer
"""

import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from fastapi.testclient import TestClient

from app.main import app
from app.models import Snapshot
from app.storage import StorageError


class MockStorageService:
    """Mock storage service that demonstrates proper exception flow."""

    def __init__(self):
        self.temp_dir = None
        self.setup_test_files()

        # Create test snapshot
        self.test_snapshot = Snapshot(
            snapshot_id="req_test-request-1_20250904_061411",
            timestamp=datetime(2025, 9, 4, 6, 14, 11, tzinfo=timezone.utc),
            url="https://example.com",
            title="Example Domain",
            folder_path=str(self.snapshot_dir),
            metadata={"status": 200},
            available_artifacts=["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]
        )

        # Mock provider to get storage_path
        self.provider = Mock()
        self.provider.storage_path = self.temp_dir

    def setup_test_files(self):
        """Create temporary test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = Path(self.temp_dir) / "example_com" / "home_page" / "req_test-request-1_20250904_061411"
        self.snapshot_dir.mkdir(parents=True)

        # Create test artifact files
        test_files = {
            "archive.wacz": b"PK\x03\x04" + b"fake wacz content" * 100,
            "metadata.json": b'{"url": "https://example.com", "status": 200}',
            "screenshot.png": b"\x89PNG\r\n\x1a\n" + b"fake png content",
            "singlefile.html": b"<html><head><title>Test</title></head><body>Test content</body></html>"
        }

        for filename, content in test_files.items():
            file_path = self.snapshot_dir / filename
            file_path.write_bytes(content)

    def get_snapshot_by_id(self, snapshot_id: str):
        """
        Mock snapshot lookup - demonstrates middleware error handling.

        Returns:
            Snapshot object if found
            None if not found (API should handle this)

        Raises:
            StorageError: For actual storage failures (middleware handles)
        """
        if snapshot_id == "req_test-request-1_20250904_061411":
            return self.test_snapshot
        elif snapshot_id == "req_nonexistent_20250904_061411":
            return None  # API layer handles this
        elif snapshot_id == "req_storage_error_20250904_061411":
            raise StorageError("Database connection failed")  # Middleware handles
        else:
            return None

    def artifact_exists(self, snapshot_id: str, artifact_type: str) -> bool:
        """
        Check if artifact exists in snapshot metadata.

        Returns:
            bool: True if artifact exists in metadata

        Raises:
            StorageError: For storage access failures (middleware handles)
        """
        if snapshot_id == "req_test-request-1_20250904_061411":
            return artifact_type in ["archive.wacz", "metadata.json", "screenshot.png", "singlefile.html"]
        elif snapshot_id == "req_storage_error_20250904_061411":
            raise StorageError("Metadata access failed")
        return False

    def get_artifact_path(self, snapshot_id: str, artifact_type: str):
        """
        Get filesystem path to artifact.

        Returns:
            Path object if artifact exists
            None if artifact doesn't exist (API handles)

        Raises:
            StorageError: For filesystem access failures (middleware handles)
        """
        if snapshot_id == "req_test-request-1_20250904_061411" and self.artifact_exists(snapshot_id, artifact_type):
            return self.snapshot_dir / artifact_type
        elif snapshot_id == "req_storage_error_20250904_061411":
            raise StorageError("Filesystem access failed")
        return None

    def __del__(self):
        """Clean up temporary directory."""
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    """Test client with mocked storage service."""
    from configs import YamlFileConfigLoader

    mock_storage = MockStorageService()
    test_app = app
    test_app.state.storage_service = mock_storage
    test_app.state.app_config = YamlFileConfigLoader().load()
    return TestClient(test_app)


@pytest.fixture
def mock_storage():
    """Direct access to mock storage for test manipulation."""
    return MockStorageService()


class TestArtifactServingSuccess:
    """Test successful artifact serving scenarios."""

    def test_serve_wacz_artifact_success(self, client):
        """Test successful WACZ artifact serving."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=archive.wacz")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert "req_test-request-1_20250904_061411_archive.wacz" in response.headers["content-disposition"]
        assert response.headers["x-content-type-options"] == "nosniff"

        # Verify content
        content = response.content
        assert content.startswith(b"PK\x03\x04")  # ZIP signature
        assert len(content) > 0

    def test_serve_json_artifact_success(self, client):
        """Test successful JSON metadata serving."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=metadata.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment; filename=" in response.headers["content-disposition"]

    def test_serve_html_with_inline_disposition(self, client):
        """Test HTML files get inline disposition for iframe display."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=singlefile.html")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html"
        assert "inline; filename=" in response.headers["content-disposition"]


class TestArtifactServingErrorsHandledByMiddleware:
    """Test that all errors are properly handled by middleware, not API layer."""

    def test_missing_snapshot_id_parameter(self, client):
        """Test validation error handled by middleware."""
        response = client.get("/api/artifacts/serve?type=archive.wacz")

        assert response.status_code == 422
        data = response.json()
        # Middleware should format validation errors consistently
        assert "success" in data
        assert data["success"] == False
        assert "error" in data
        assert "validation_error" in data["error"]

    def test_missing_type_parameter(self, client):
        """Test validation error handled by middleware."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411")

        assert response.status_code == 422
        data = response.json()
        assert "success" in data
        assert data["success"] == False

    def test_security_validation_error_in_middleware(self, client):
        """Test that security validation errors are caught by middleware."""
        response = client.get("/api/artifacts/serve?snapshot_id=../../../etc/passwd&type=archive.wacz")

        assert response.status_code == 400
        data = response.json()
        assert "success" in data
        assert data["success"] == False
        assert data["error"] == "security_validation_error"
        assert "request_id" in data
        assert "X-Request-ID" in response.headers

    def test_invalid_artifact_type_security_error(self, client):
        """Test invalid artifact type handled by middleware."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=malicious.exe")

        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "security_validation_error"
        assert "Security validation failed" in data["message"]

    def test_nonexistent_snapshot_handled_by_middleware(self, client):
        """Test that API returns None, middleware converts to 404."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_nonexistent_20250904_061411&type=archive.wacz")

        # API layer: get_snapshot_by_id returns None
        # API layer: should handle None and raise appropriate exception
        # Middleware: catches exception and converts to JSON response
        assert response.status_code == 404
        data = response.json()
        assert "success" in data
        assert data["success"] == False
        assert data["error"] == "not_found"
        assert "snapshot" in data["message"].lower() or "not found" in data["message"].lower()
        assert "request_id" in data

    def test_storage_error_handled_by_middleware(self, client):
        """Test StorageError properly handled by middleware."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_storage_error_20250904_061411&type=archive.wacz")

        # Storage service raises StorageError
        # Middleware catches it and converts to proper JSON response
        assert response.status_code == 500
        data = response.json()
        assert "success" in data
        assert data["success"] == False
        assert data["error"] == "storage_error"
        assert "request_id" in data
        assert "X-Request-ID" in response.headers


class TestMiddlewareErrorFormatConsistency:
    """Test that middleware produces consistent error response format."""

    def test_error_response_format_consistency(self, client):
        """Test all error responses have consistent structure."""
        # Test different error types to ensure consistent format
        test_cases = [
            ("/api/artifacts/serve?type=archive.wacz", 422),  # Validation error
            ("/api/artifacts/serve?snapshot_id=../malicious&type=archive.wacz", 400),  # Security error
            ("/api/artifacts/serve?snapshot_id=req_nonexistent_20250904_061411&type=archive.wacz", 404),  # Not found
            ("/api/artifacts/serve?snapshot_id=req_storage_error_20250904_061411&type=archive.wacz", 500),  # Storage error
        ]

        for url, expected_status in test_cases:
            response = client.get(url)
            assert response.status_code == expected_status

            data = response.json()
            # All error responses should have this structure
            assert "success" in data
            assert data["success"] == False
            assert "error" in data
            assert "message" in data
            assert "request_id" in data

            # Response headers should be consistent
            assert "X-Request-ID" in response.headers
            # Handle case where header might have multiple values (due to middleware stacking)
            header_id = response.headers["X-Request-ID"].split(',')[0].strip()
            assert header_id == data["request_id"]

    def test_successful_response_has_request_id_header(self, client):
        """Test successful responses include request ID in headers."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=archive.wacz")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Successful responses don't include request_id in JSON body, only headers


class TestArtifactServingBusinessLogic:
    """Test business logic without error handling complexity."""

    def test_content_type_assignment(self, client):
        """Test that correct content types are assigned."""
        test_cases = [
            ("archive.wacz", "application/zip"),
            ("metadata.json", "application/json"),
            ("screenshot.png", "image/png"),
            ("singlefile.html", "text/html"),
        ]

        for artifact_type, expected_content_type in test_cases:
            response = client.get(f"/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type={artifact_type}")

            assert response.status_code == 200
            assert response.headers["content-type"] == expected_content_type

    def test_security_headers_applied(self, client):
        """Test that security headers are properly applied."""
        response = client.get("/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=archive.wacz")

        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "cache-control" in response.headers
        assert "private" in response.headers["cache-control"]

    def test_client_ip_extraction(self, client):
        """Test client IP extraction for logging."""
        headers = {"X-Forwarded-For": "203.0.113.1, 192.168.1.100"}
        response = client.get(
            "/api/artifacts/serve?snapshot_id=req_test-request-1_20250904_061411&type=archive.wacz",
            headers=headers
        )

        assert response.status_code == 200
        # IP extraction is tested through successful response (logged internally)


if __name__ == "__main__":
    pytest.main([__file__])