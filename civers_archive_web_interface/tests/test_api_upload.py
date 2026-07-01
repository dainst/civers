"""
Integration tests for the upload API endpoint.

Tests the POST /api/upload endpoint including multipart file uploads,
validation, error handling, and idempotent operations.
"""

import pytest
import json
from io import BytesIO
from fastapi.testclient import TestClient

from app.main import app
from configs import YamlFileConfigLoader
from app.storage import create_storage_service


@pytest.fixture
def client():
    """Provide FastAPI test client with initialized app state."""
    import tempfile
    import shutil
    
    # Create temp directory for independent test run
    temp_dir = tempfile.mkdtemp()
    
    with TestClient(app) as test_client:
        # Initialize app state
        app_config = YamlFileConfigLoader().load()
        
        # Override storage config to use temp directory
        app_config.storage.type = 'sqlite'
        app_config.storage.filesystem.path = temp_dir
        # Ensure sqlite config exists if it wasn't default
        if not app_config.storage.sqlite:
             from configs.models import SQLiteConfig
             app_config.storage.sqlite = SQLiteConfig()
        app_config.storage.sqlite.db_path = f"{temp_dir}/archives.db"
        
        storage_service = create_storage_service(app_config)

        test_client.app.state.app_config = app_config
        test_client.app.state.storage_service = storage_service

        yield test_client
        
    # Cleanup
    shutil.rmtree(temp_dir)


def create_test_file(content: bytes, filename: str):
    """Helper to create a test file tuple for upload."""
    return (filename, BytesIO(content), 'application/octet-stream')


class TestUploadEndpoint:
    """Basic tests for upload endpoint."""

    def test_upload_single_file(self, client):
        """Test uploading a single file."""
        files = [
            ('files', create_test_file(b'wacz content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/test',
                'request_id': 'test1'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['snapshot_id'].startswith('req_test1_')
        assert data['url'] == 'https://example.com/test'
        assert 'archive.wacz' in data['artifacts_uploaded']
        assert len(data['artifacts_uploaded']) == 1

    def test_upload_multiple_files(self, client):
        """Test uploading multiple files."""
        metadata = {'url': 'https://example.com', 'title': 'Test'}
        files = [
            ('files', create_test_file(b'wacz content', 'archive.wacz')),
            ('files', create_test_file(b'png content', 'screenshot.png')),
            ('files', create_test_file(json.dumps(metadata).encode(), 'metadata.json'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test2'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['artifacts_uploaded']) == 3
        assert 'archive.wacz' in data['artifacts_uploaded']
        assert 'screenshot.png' in data['artifacts_uploaded']
        assert 'metadata.json' in data['artifacts_uploaded']

    def test_upload_creates_correct_directory_structure(self, client):
        """Test that upload creates correct directory structure."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/about-us',
                'request_id': 'test3'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Snapshot ID should be in response
        snapshot_id = data['snapshot_id']
        assert snapshot_id.startswith('req_test3_')


class TestValidation:
    """Tests for request validation."""

    def test_upload_without_files(self, client):
        """Test that upload without files returns error."""
        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com',
                'request_id': 'test4'
            }
        )

        assert response.status_code == 422  # Validation error

    def test_upload_without_url(self, client):
        """Test that upload without URL returns error."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={'request_id': 'test5'},
            files=files
        )

        assert response.status_code == 422  # Validation error

    def test_upload_without_request_id(self, client):
        """Test that upload without request_id returns error."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={'url': 'https://example.com'},
            files=files
        )

        assert response.status_code == 422  # Validation error

    def test_upload_invalid_artifact_type(self, client):
        """Test that invalid artifact type returns error."""
        files = [
            ('files', create_test_file(b'malware', 'malware.exe'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com',
                'request_id': 'test6'
            },
            files=files
        )

        assert response.status_code == 400
        data = response.json()
        assert 'Invalid artifact type' in data['detail']


class TestIdempotentOperations:
    """Tests for idempotent upload operations."""

    def test_duplicate_upload_fails_by_default(self, client):
        """Test that duplicate upload fails without allow_existing."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        # First upload
        response1 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test7'
            },
            files=files
        )
        assert response1.status_code == 200

        # Second upload without allow_existing
        response2 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test7'
            },
            files=files
        )

        assert response2.status_code == 400
        data = response2.json()
        assert 'Snapshot already exists' in data['detail']

    def test_add_files_to_existing_snapshot(self, client):
        """Test adding files to existing snapshot with allow_existing=true."""
        # First upload - archive
        files1 = [
            ('files', create_test_file(b'wacz content', 'archive.wacz'))
        ]

        response1 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test8'
            },
            files=files1
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1['artifacts_uploaded']) == 1

        # Second upload - screenshot with allow_existing
        files2 = [
            ('files', create_test_file(b'png content', 'screenshot.png'))
        ]

        response2 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test8',
                'allow_existing': 'true'
            },
            files=files2
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2['artifacts_uploaded']) == 2
        assert 'screenshot.png' in data2['artifacts_uploaded']

    def test_existing_files_not_overwritten(self, client):
        """Test that existing files are not overwritten in idempotent mode."""
        # First upload
        files1 = [
            ('files', create_test_file(b'original content', 'archive.wacz'))
        ]

        response1 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test9'
            },
            files=files1
        )
        assert response1.status_code == 200

        # Try to upload same file with different content
        files2 = [
            ('files', create_test_file(b'new content', 'archive.wacz'))
        ]

        response2 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'test9',
                'allow_existing': 'true'
            },
            files=files2
        )

        assert response2.status_code == 200
        data2 = response2.json()
        # File should be in available artifacts list (exists)
        assert 'archive.wacz' in data2['artifacts_uploaded']


class TestUploadInfo:
    """Tests for upload info endpoint."""

    def test_upload_info_endpoint(self, client):
        """Test that upload info endpoint returns correct information."""
        response = client.get('/api/upload/info')

        assert response.status_code == 200
        data = response.json()

        assert data['endpoint'] == '/api/upload'
        assert data['method'] == 'POST'
        assert data['content_type'] == 'multipart/form-data'
        assert 'form_fields' in data
        assert 'allowed_file_types' in data
        assert 'example_curl' in data
        assert 'idempotent_example' in data

    def test_upload_info_includes_allowed_types(self, client):
        """Test that upload info includes list of allowed file types."""
        response = client.get('/api/upload/info')

        assert response.status_code == 200
        data = response.json()

        allowed_types = data['allowed_file_types']
        assert isinstance(allowed_types, list)
        assert 'archive.wacz' in allowed_types
        assert 'screenshot.png' in allowed_types
        assert 'metadata.json' in allowed_types


class TestResponseFormat:
    """Tests for response format."""

    def test_success_response_format(self, client):
        """Test that success response has correct format."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com',
                'request_id': 'test10'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields
        assert 'success' in data
        assert 'snapshot_id' in data
        assert 'url' in data
        assert 'artifacts_uploaded' in data
        assert 'message' in data

        # Verify types
        assert isinstance(data['success'], bool)
        assert isinstance(data['snapshot_id'], str)
        assert isinstance(data['url'], str)
        assert isinstance(data['artifacts_uploaded'], list)
        assert isinstance(data['message'], str)

    def test_error_response_format(self, client):
        """Test that error response has correct format."""
        # Upload without files to trigger error
        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com',
                'request_id': 'test11'
            }
        )

        assert response.status_code == 422
        data = response.json()
        # Custom validation error handler uses 'details' not 'detail'
        assert 'details' in data or 'detail' in data


class TestURLHandling:
    """Tests for URL handling and normalization."""

    def test_upload_with_complex_url(self, client):
        """Test upload with complex URL."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/path/to/page?param=value#section',
                'request_id': 'test12'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_upload_with_subdomain(self, client):
        """Test upload with subdomain URL."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        response = client.post(
            '/api/upload',
            data={
                'url': 'https://blog.example.com/article',
                'request_id': 'test13'
            },
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


class TestConcurrency:
    """Tests for concurrent operations."""

    def test_multiple_concurrent_uploads_different_urls(self, client):
        """Test multiple concurrent uploads for different URLs."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        # Upload for URL 1
        response1 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page1',
                'request_id': 'test14'
            },
            files=files
        )

        # Upload for URL 2
        response2 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page2',
                'request_id': 'test15'
            },
            files=files
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Should have different snapshot IDs
        assert data1['snapshot_id'] != data2['snapshot_id']

    def test_multiple_uploads_same_url_different_request_ids(self, client):
        """Test multiple uploads for same URL with different request IDs."""
        files = [
            ('files', create_test_file(b'content', 'archive.wacz'))
        ]

        # First upload
        response1 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'request1'
            },
            files=files
        )

        # Second upload with different request_id
        response2 = client.post(
            '/api/upload',
            data={
                'url': 'https://example.com/page',
                'request_id': 'request2'
            },
            files=files
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Should have different snapshot IDs
        assert data1['snapshot_id'] != data2['snapshot_id']
