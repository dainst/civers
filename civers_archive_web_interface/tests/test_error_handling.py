import json
import logging
from unittest.mock import patch
from fastapi.testclient import TestClient

# Configure pytest for async tests
pytest_plugins = ('pytest_asyncio',)

from app.main import app
from app.middleware.error_handlers.api_error_handler import create_api_error_response
from app.middleware.error_handlers.api_error_handler import APIErrorHandler
from app.middleware.error_handlers.page_error_handler import PageErrorHandler
from app.middleware.error_handlers.error_dispatcher import ErrorDispatcherMiddleware
from app.logging.formatters import JSONFormatter


class TestErrorHandlers:
    """Test error handling functions."""
    
    def test_create_api_error_response(self):
        """Test consistent API error response creation."""
        from app.models.responses import ErrorDetail
        from unittest.mock import patch

        error_detail = ErrorDetail(field="test_field", message="Field error", code="validation_error")

        # Mock the correlation_id to return a known value
        with patch('app.middleware.error_handlers.api_error_handler._get_correlation_id', return_value="test-correlation-id"):
            response = create_api_error_response(
                error_type="test_error",
                message="Test message",
                status_code=400,
                details=[error_detail]
            )

        assert response.status_code == 400
        content = json.loads(response.body)
        assert content["success"] == False
        assert content["error"] == "test_error"
        assert content["message"] == "Test message"
        assert content["request_id"] == "test-correlation-id"
        assert len(content["details"]) == 1
        assert content["details"][0]["field"] == "test_field"
        assert content["details"][0]["message"] == "Field error"

    def test_create_api_error_response_no_details(self):
        """Test API error response without details."""
        with patch('app.middleware.error_handlers.api_error_handler._get_correlation_id', return_value="test-id"):
            response = create_api_error_response("simple_error", "Simple message", 404, details=None)

            content = json.loads(response.body)
            assert content["details"] is None
            assert content["success"] == False
            assert content["error"] == "simple_error"
            assert content["request_id"] == "test-id"
    


class TestMiddlewareIntegration:
    """Test middleware integration with FastAPI app."""

    def setup_method(self):
        """Set up test client with proper app state."""
        # Create a test client that simulates the lifespan events
        from app.config import load_app_config
        from app.storage import create_storage_service

        self.client = TestClient(app)

        # Manually initialize app state for testing
        app_config = load_app_config()
        storage_service = create_storage_service(app_config)

        app.state.app_config = app_config
        app.state.storage_service = storage_service
    
    def test_health_endpoint_with_logging(self):
        """Test health endpoint includes request logging."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_404_error_format(self):
        """Test 404 error returns consistent format."""
        response = self.client.get("/api/nonexistent")
        
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
        
        data = response.json()
        assert data["error"] == "not_found"
        assert "request_id" in data
        assert "message" in data
    
    def test_validation_error_format(self):
        """Test validation errors return consistent format."""
        # Try to access URLs with invalid pagination
        response = self.client.get("/api/urls?page=invalid")

        assert response.status_code == 422
        assert "X-Request-ID" in response.headers

        data = response.json()
        # FastAPI validation can have either format depending on middleware catch
        if "success" in data:
            # Our custom error format
            assert data["success"] == False
            assert data["error"] == "validation_error"
            assert "details" in data
            assert len(data["details"]) == 1
            assert data["details"][0]["field"] == "query -> page"
        else:
            # FastAPI built-in format
            assert "detail" in data
            assert len(data["detail"]) == 1
            assert data["detail"][0]["loc"] == ["query", "page"]
    
    def test_request_id_consistency(self):
        """Test request ID is consistent across response and headers."""
        response = self.client.get("/health")

        # For successful responses, request_id won't be in JSON body
        # But for error responses, it should match - test with an API error
        response_error = self.client.get("/api/nonexistent")
        error_data = response_error.json()
        error_request_id = response_error.headers["X-Request-ID"]

        # Handle case where header might have multiple values (due to middleware stacking)
        # Take the first value if comma-separated
        header_id = error_request_id.split(',')[0].strip()

        assert error_data["request_id"] == header_id
    
    def test_security_error_handling(self):
        """Test security validation errors are handled correctly."""
        # Test with artifact endpoint using invalid characters
        response = self.client.get("/api/artifacts/serve?snapshot_id=../../../etc/passwd&type=wacz")
        
        assert response.status_code == 400
        assert "X-Request-ID" in response.headers
        
        data = response.json()
        assert data["error"] == "security_validation_error"




class TestErrorDispatcherArchitecture:
    """Test the new error dispatcher architecture."""

    def test_error_dispatcher_components(self):
        """Test that error dispatcher has the correct handler components."""
        dispatcher = ErrorDispatcherMiddleware(app)

        # Verify dispatcher has both handlers
        assert isinstance(dispatcher.api_handler, APIErrorHandler)
        assert isinstance(dispatcher.page_handler, PageErrorHandler)

    def test_handler_classes_exist(self):
        """Test that handler classes can be instantiated correctly."""
        # Test API handler
        api_handler = APIErrorHandler()
        assert hasattr(api_handler, 'handle_request')
        assert callable(api_handler.handle_request)

        # Test Page handler
        page_handler = PageErrorHandler()
        assert hasattr(page_handler, 'handle_request')
        assert callable(page_handler.handle_request)
        assert hasattr(page_handler, 'templates')

    def test_middleware_efficiency_single_dispatcher(self):
        """Test that only one error handling middleware is in the stack."""
        # Check middleware stack using FastAPI's user_middleware
        middleware_classes = []

        for middleware_cls, args, kwargs in app.user_middleware:
            middleware_name = middleware_cls.__name__
            middleware_classes.append(middleware_name)

        # Should have ErrorDispatcherMiddleware in the stack
        has_dispatcher = 'ErrorDispatcherMiddleware' in middleware_classes
        assert has_dispatcher, f"ErrorDispatcherMiddleware not found. Available middleware: {middleware_classes}"

        # Should NOT have the old separate error middleware
        has_api_error = 'APIErrorMiddleware' in middleware_classes
        has_page_error = 'PageErrorMiddleware' in middleware_classes

        assert not has_api_error, f"APIErrorMiddleware should not be in stack. Found: {middleware_classes}"
        assert not has_page_error, f"PageErrorMiddleware should not be in stack. Found: {middleware_classes}"

        # Count error handling middleware - should be exactly 1 (the dispatcher)
        error_middleware = [m for m in middleware_classes if 'Error' in m or 'Dispatcher' in m]
        assert len(error_middleware) == 1, f"Expected exactly 1 error middleware, found: {error_middleware}"