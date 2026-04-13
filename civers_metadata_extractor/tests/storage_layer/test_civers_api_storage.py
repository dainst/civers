"""
Tests for CIVERS REST API Storage Strategy.

Tests the CiversRestApiStorageStrategy implementation including successful uploads,
retry logic, authentication, error handling, and availability checking.
Uses pytest-httpx for mocking HTTP responses.
"""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from storage_layer.civers_rest_api_storage_strategy import CiversRestApiStorageStrategy


class TestCiversRestApiStorageStrategy:
    """Test cases for CiversRestApiStorageStrategy."""

    @pytest.mark.asyncio
    async def test_successful_upload(self, httpx_mock: HTTPXMock):
        """Test successful metadata upload to CIVERS API."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url)

        # Mock successful API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={
                "success": True,
                "snapshot_id": "test_snapshot_123",
                "url": "https://example.com",
                "artifacts_uploaded": ["metadata.json"],
                "message": "Files uploaded successfully",
            },
            status_code=200,
        )

        data = {"title": "Test Data", "description": "Test"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_001", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True
        assert result.storage_type == "civers_rest_api"
        assert result.storage_location == "test_snapshot_123"
        assert result.metadata["snapshot_id"] == "test_snapshot_123"
        assert result.metadata["upload_url"] == upload_url
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_upload_with_bearer_auth(self, httpx_mock: HTTPXMock):
        """Test upload with Bearer token authentication."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        auth_config = {"enabled": True, "type": "bearer", "token": "test_bearer_token_123"}
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, auth=auth_config)

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_001"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_001", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True

        # Verify auth header was sent
        request = httpx_mock.get_request()
        assert request.headers.get("Authorization") == "Bearer test_bearer_token_123"

    @pytest.mark.asyncio
    async def test_upload_with_api_key_auth(self, httpx_mock: HTTPXMock):
        """Test upload with API key authentication."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        auth_config = {"enabled": True, "type": "api_key", "token": "test_api_key_456"}
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, auth=auth_config)

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_002"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_002", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True

        # Verify API key header was sent
        request = httpx_mock.get_request()
        assert request.headers.get("X-API-Key") == "test_api_key_456"

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, httpx_mock: HTTPXMock):
        """Test retry logic when server returns 5xx error."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, retry_attempts=3)

        # Mock: First two attempts fail with 500, third succeeds
        httpx_mock.add_response(
            url=upload_url, method="POST", status_code=500, text="Internal Server Error"
        )
        httpx_mock.add_response(
            url=upload_url, method="POST", status_code=500, text="Internal Server Error"
        )
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_retry"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_retry", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True
        assert result.metadata["attempt"] == 3  # Succeeded on 3rd attempt

        # Verify 3 requests were made
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, httpx_mock: HTTPXMock):
        """Test that 4xx errors don't trigger retries."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, retry_attempts=3)

        # Mock 400 Bad Request
        httpx_mock.add_response(
            url=upload_url, method="POST", status_code=400, text="Bad Request: Invalid data"
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_400", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is False
        assert "HTTP 400" in result.error_message

        # Verify only 1 request was made (no retries for 4xx)
        requests = httpx_mock.get_requests()
        assert len(requests) == 1

    @pytest.mark.asyncio
    async def test_all_retries_fail(self, httpx_mock: HTTPXMock):
        """Test when all retry attempts fail."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, retry_attempts=3)

        # Mock: All attempts return 503 Service Unavailable
        for _ in range(3):
            httpx_mock.add_response(
                url=upload_url, method="POST", status_code=503, text="Service Unavailable"
            )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_fail", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is False
        assert "All 3 upload attempts failed" in result.error_message
        assert result.metadata["attempts"] == 3

        # Verify 3 requests were made
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

    @pytest.mark.asyncio
    async def test_timeout_handling(self, httpx_mock: HTTPXMock):
        """Test handling of request timeouts."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(
            upload_url=upload_url, timeout_seconds=1, retry_attempts=2
        )

        # Mock: Callback that raises TimeoutException - need to add it twice for retries
        def timeout_callback(request):
            raise httpx.TimeoutException("Request timed out")

        httpx_mock.add_callback(timeout_callback, url=upload_url)
        httpx_mock.add_callback(timeout_callback, url=upload_url)

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_timeout", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is False
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_is_available_connection_error(self, httpx_mock: HTTPXMock):
        """Test is_available when connection fails."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url)

        # Mock: Callback that raises ConnectError
        def connection_error_callback(request):
            raise httpx.ConnectError("Connection failed")

        httpx_mock.add_callback(connection_error_callback, url=upload_url, method="OPTIONS")

        # Act
        available = await strategy.is_available()

        # Assert
        assert available is False

    @pytest.mark.asyncio
    async def test_custom_timeout(self, httpx_mock: HTTPXMock):
        """Test that custom timeout is respected."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        custom_timeout = 60
        strategy = CiversRestApiStorageStrategy(
            upload_url=upload_url, timeout_seconds=custom_timeout
        )

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_timeout"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data,
            request_id="req_timeout_test",
            url="https://example.com",
            filename="metadata.json",
        )

        # Assert
        assert result.success is True

    @pytest.mark.asyncio
    async def test_ssl_verification_disabled(self, httpx_mock: HTTPXMock):
        """Test that SSL verification can be disabled."""
        # Arrange
        upload_url = "https://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, verify_ssl=False)

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_no_ssl"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_no_ssl", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handles_unicode_data(self, httpx_mock: HTTPXMock):
        """Test upload of metadata with unicode characters."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url)

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_unicode"},
            status_code=200,
        )

        data = {"title": "Archäologisches Objekt", "description": "测试数据 🏛️"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_unicode", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True

    @pytest.mark.asyncio
    async def test_metadata_serialization_error(self):
        """Test handling of data that cannot be serialized to JSON."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url)

        # Create non-serializable data (circular reference)
        circular_data = {}
        circular_data["self"] = circular_data

        # Act
        result = await strategy.store_metadata(
            data=circular_data,
            request_id="req_circular",
            url="https://example.com",
            filename="metadata.json",
        )

        # Assert
        assert result.success is False
        assert "serialize" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_no_auth_when_disabled(self, httpx_mock: HTTPXMock):
        """Test that no auth headers are sent when auth is disabled."""
        # Arrange
        upload_url = "http://localhost:8000/api/upload"
        auth_config = {"enabled": False}
        strategy = CiversRestApiStorageStrategy(upload_url=upload_url, auth=auth_config)

        # Mock API response
        httpx_mock.add_response(
            url=upload_url,
            method="POST",
            json={"success": True, "snapshot_id": "snap_no_auth"},
            status_code=200,
        )

        data = {"test": "data"}

        # Act
        result = await strategy.store_metadata(
            data=data, request_id="req_no_auth", url="https://example.com", filename="metadata.json"
        )

        # Assert
        assert result.success is True

        # Verify no auth headers
        request = httpx_mock.get_request()
        assert "Authorization" not in request.headers
        assert "X-API-Key" not in request.headers


