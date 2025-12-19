# Error Handling Documentation

## Overview

The Civers Web Interface handles errors at two different levels to provide consistent responses across both API and page routes:

1. **Application-Level Errors**: FastAPI routing and validation errors
2. **Business Logic Errors**: Custom exceptions that happen during request processing

**How it works:**
- API routes return JSON error responses, pages return HTML error pages
- All error handling is centralized in middleware and exception handlers
- API routes throw business exceptions without worrying about response formatting
- Every error response includes correlation IDs for tracking

## File Structure

### Custom Exceptions (`app/custom_exceptions/`)
```
custom_exceptions/
├── handlers.py                    (55 lines - Application-level exception handlers)
└── exceptions/
    └── api_exceptions.py          (32 lines - Custom business exception classes)
```

### Error Handling Middleware (`app/middleware/error_handlers/`)
```
error_handlers/
├── __init__.py                    (1 line  - Package exports)
├── error_dispatcher.py            (78 lines - Routes errors to appropriate handler)
├── api_error_handler.py           (180 lines - Handles API errors as JSON)
└── page_error_handler.py          (67 lines - Handles page errors as HTML)
```

**Total Exception Classes:** 3
**Total Error Handlers:** 3
**Total Lines of Code:** 413 lines

## Two-Level Error Handling

### Level 1: Application Errors (FastAPI)

FastAPI handles routing errors and validation errors at the application level:

```python
# In app/main.py - registered as application exception handler
app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)
```

This catches things like:
- Invalid URLs (404 errors)
- Request validation failures (missing parameters, wrong types)
- FastAPI internal routing errors

### Level 2: Business Logic Errors (ErrorDispatcherMiddleware)

The `ErrorDispatcherMiddleware` catches exceptions that happen during request processing:

```python
class ErrorDispatcherMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Route to appropriate handler based on path
            if request.url.path.startswith('/api/'):
                handler = self.api_handler
            else:
                handler = self.page_handler
            return await handler.handle_request(request, exc)
```

This catches custom business exceptions like missing resources or validation errors.

## Custom Exception Classes

### 1. ResourceNotFoundError

**File:** `app/custom_exceptions/exceptions/api_exceptions.py`

```python
class ResourceNotFoundError(Exception):
    """Raised when a requested resource (URL, snapshot, artifact) is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found")
```

**What it's for:** When any resource in the archive system can't be found

**Used for:**
- Missing URLs in the archive
- Non-existent snapshots
- Invalid resource identifiers

**Example:**
```python
# From /app/api/urls.py
if not archived_url:
    raise ResourceNotFoundError("URL", url_id)

# From /app/api/snapshot_detail.py
if not snapshot:
    raise ResourceNotFoundError("Snapshot", snapshot_id)
```

### 2. ArtifactNotFoundError

**File:** `app/custom_exceptions/exceptions/api_exceptions.py`

```python
class ArtifactNotFoundError(Exception):
    """Raised when a specific artifact is not found for a snapshot."""

    def __init__(self, artifact_type: str, snapshot_id: str):
        self.artifact_type = artifact_type
        self.snapshot_id = snapshot_id
        super().__init__(f"Artifact '{artifact_type}' not found for snapshot '{snapshot_id}'")
```

**What it's for:** When a specific file is missing from a snapshot

**Used for:**
- Missing HTML files in a snapshot
- Missing screenshot files
- Corrupted or deleted snapshot files

**Example:**
```python
# From /app/api/artifacts.py
if not storage_service.artifact_exists(validated_snapshot_id, validated_artifact_type):
    raise ArtifactNotFoundError(validated_artifact_type, validated_snapshot_id)
```

### 3. ValidationError

**File:** `app/custom_exceptions/exceptions/api_exceptions.py`

```python
class ValidationError(Exception):
    """Raised when request parameters fail validation."""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message)
```

**What it's for:** Custom validation errors beyond FastAPI's automatic validation

**Used for:**
- Page number validation in pagination
- Complex parameter validation
- Business rule violations

**Example:**
```python
# From /app/api/urls.py
if page > 1 and start_idx >= total_count:
    total_pages = math.ceil(total_count / limit)
    raise ValidationError(f"Page {page} does not exist. Total pages: {total_pages}")
```

## Error Handling Middleware

### ErrorDispatcherMiddleware

**File:** `app/middleware/error_handlers/error_dispatcher.py`

This middleware sits in the request processing pipeline and catches exceptions that happen during business logic execution:

```python
class ErrorDispatcherMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.api_handler = APIErrorHandler()
        self.page_handler = PageErrorHandler()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Route to appropriate handler based on request path
            if request.url.path.startswith('/api/'):
                handler = self.api_handler
            else:
                handler = self.page_handler

            return await handler.handle_request(request, exc)
```

**How it works:** One path check routes errors to either JSON (API) or HTML (page) handlers.

### APIErrorHandler

**File:** `app/middleware/error_handlers/api_error_handler.py`

Handles all API errors and returns JSON responses:

```python
class APIErrorHandler:
    async def handle_request(self, request: Request, exc: Exception) -> JSONResponse:
        # Handle different exception types
        if isinstance(exc, ResourceNotFoundError):
            return await self._handle_resource_not_found_error(request, exc)
        elif isinstance(exc, ArtifactNotFoundError):
            return await self._handle_artifact_not_found_error(request, exc)
        elif isinstance(exc, ValidationError):
            return await self._handle_api_validation_error(request, exc)
        # ... handles other exception types
```

### PageErrorHandler

**File:** `app/middleware/error_handlers/page_error_handler.py`

Handles page errors and returns HTML responses:

```python
class PageErrorHandler:
    async def handle_request(self, request: Request, exc: Exception) -> Response:
        # Handle different exception types for HTML pages
        if isinstance(exc, (ResourceNotFoundError, ArtifactNotFoundError)):
            return await self._handle_not_found_error(request, exc)
        elif isinstance(exc, ValidationError):
            return await self._handle_validation_error(request, exc)
        # ... handles other exception types
```

### Application-Level Handler

**File:** `app/custom_exceptions/handlers.py`

Handles FastAPI routing and validation errors:

```python
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    # For API routes, use our middleware's validation error handler
    if request.url.path.startswith('/api/'):
        api_handler = APIErrorHandler()
        return await api_handler._handle_validation_error(request, exc)

    # For page routes, use FastAPI's default handler
    return await request_validation_exception_handler(request, exc)
```

**Registration:** Added as FastAPI exception handler in `main.py`

## Error Flow

### How Errors Are Processed

**FastAPI Application-Level Errors:**
```
FastAPI Routing Error (404, validation errors)
    ↓
Application Exception Handler (custom_validation_exception_handler)
    ↓
Routes to appropriate handler based on path (/api/* vs pages)
```

**Business Logic Errors:**
```
Business Logic Exception (ResourceNotFoundError, ValidationError)
    ↓
ErrorDispatcherMiddleware catches during request processing
    ↓
Path-based routing (/api/* vs pages)
    ↓
Specialized Handler (APIErrorHandler vs PageErrorHandler)
    ↓
Formatted Response (JSON with ErrorResponse vs HTML template)
    ↓
Correlation ID Tracking + Structured Logging
```

### Request Processing Order

```
1. FastAPI processes the request
   ├─ Route matching and parameter validation
   ├─ Application exception handlers catch routing errors

2. Middleware stack processes the request
   ├─ ErrorDispatcherMiddleware catches business logic errors
   ├─ Routes to APIErrorHandler (JSON) or PageErrorHandler (HTML)

3. Route handler executes
   ├─ Business logic runs
   ├─ May throw custom exceptions
   ├─ Middleware catches and formats responses
```

## Error Response Format

### API Error Responses

All API errors return JSON using the `ErrorResponse` model:

```python
class ErrorResponse(BaseModel):
    success: bool = False                    # Always false for errors
    error: str                              # Brief error type
    message: str                            # Detailed error message
    details: Optional[List[ErrorDetail]]    # Additional error details
    request_id: Optional[str]               # Correlation ID for tracking
```

### Error Details

```python
class ErrorDetail(BaseModel):
    field: Optional[str]        # Field that caused error
    message: str               # Human-readable error message
    code: Optional[str]        # Machine-readable error code
```

### Example API Error Response

```json
{
  "success": false,
  "error": "not_found",
  "message": "Snapshot '20240315T143022Z' not found",
  "details": [
    {
      "field": "snapshot_id",
      "message": "Snapshot '20240315T143022Z' not found",
      "code": "snapshot_not_found"
    }
  ],
  "request_id": "req_7f8a9b2c"
}
```

## How Different Errors Are Handled

### Resource Not Found Errors

When a URL, snapshot, or other resource can't be found:

**API Response (JSON):**
```json
{
  "success": false,
  "error": "not_found",
  "message": "Snapshot 'abc123' not found",
  "details": [{
    "field": "snapshot_id",
    "message": "Snapshot 'abc123' not found",
    "code": "snapshot_not_found"
  }],
  "request_id": "req_7f8a9b2c"
}
```

**Page Response (HTML):** Returns 404.html template with error message

### Artifact Not Found Errors

When a specific file is missing from a snapshot:

**API Response:** Same JSON format as above, but with `"code": "artifact_not_found"`

**Page Response:** Returns 404.html template

### Validation Errors

When request parameters are invalid:

**API Response:** Returns 400 status with validation error details

**Page Response:** Returns error page with validation message

### HTTP Status Codes

Different exceptions map to specific HTTP status codes:

```
ResourceNotFoundError   → 404 Not Found
ArtifactNotFoundError   → 404 Not Found
ValidationError         → 400 Bad Request
StorageError           → 404/403/500 (depends on error)
SecurityValidationError → 400 Bad Request
HTTPException          → As specified
RequestValidationError → 422 Unprocessable Entity
General Exception      → 500 Internal Server Error
```

## Logging and Monitoring

### Correlation IDs

Every error response includes a correlation ID for tracking:

```python
def _get_correlation_id() -> str:
    return correlation_id.get('unknown')
```

### Error Logging

All errors are logged with structured data:

```python
logger.warning(f"API resource not found: {exc.resource_type} '{exc.resource_id}'", extra={
    'error_type': 'api_resource_not_found',
    'path': request.url.path,
    'resource_type': exc.resource_type,
    'resource_id': exc.resource_id
})
```

### Log Levels

- **500+ errors**: `logger.error()` - Server errors needing attention
- **400-499 errors**: `logger.warning()` - Client errors for monitoring
- **Request details**: Always included for debugging

## API vs Page Errors

### API Routes (/api/*)

- **Format:** JSON with `ErrorResponse` model
- **Status Codes:** Standard HTTP status codes
- **Details:** Structured `ErrorDetail` objects
- **Headers:** Include `X-Request-ID` correlation ID

### Page Routes (everything else)

- **Format:** HTML using Jinja2 templates
- **Template:** Uses `404.html` template for all errors
- **Variables:** `title`, `error_message`, `error_code`
- **Headers:** Include `X-Request-ID` correlation ID

### How Routing Works

The ErrorDispatcherMiddleware uses a simple path check:

```python
if request.url.path.startswith('/api/'):
    handler = self.api_handler  # Returns JSON
else:
    handler = self.page_handler  # Returns HTML
```

## Testing

Based on the codebase, error handling can be tested like this:

### Testing Exception Raising
```python
def test_resource_not_found_exception():
    with pytest.raises(ResourceNotFoundError) as exc_info:
        # Call API endpoint with non-existent resource
        pass

    assert exc_info.value.resource_type == "URL"
    assert exc_info.value.resource_id == "non_existent"
```

### Testing Error Response Format
```python
def test_api_error_response_format():
    response = client.get("/api/urls/non_existent")

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "not_found"
    assert "request_id" in data
```

### Testing Error Routing
```python
def test_error_dispatcher_routing():
    # API routes should return JSON
    api_response = client.get("/api/invalid")
    assert api_response.headers["content-type"] == "application/json"

    # Page routes should return HTML
    page_response = client.get("/invalid")
    assert "text/html" in page_response.headers["content-type"]
```

## Summary

The error handling system provides clean, consistent error management:

1. **Clean Separation**: Business logic throws exceptions without worrying about response formatting
2. **Consistent Responses**: All errors follow standardized formats with correlation IDs
3. **Route-Aware**: Automatically returns JSON for APIs and HTML for pages
4. **Complete Coverage**: Handles validation, business logic, storage, and system errors
5. **Monitoring Ready**: Structured logging with correlation IDs for debugging
6. **Easy to Extend**: Simple to add new exception types and handlers
7. **Production Ready**: Proper error formatting prevents information disclosure

The two-level approach effectively separates FastAPI's routing errors from business logic errors while keeping the code clean and maintainable.