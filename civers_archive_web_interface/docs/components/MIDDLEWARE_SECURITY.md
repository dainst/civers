# Security Components Documentation

## Overview

The Civers Web Interface protects against common web vulnerabilities using security headers, input validation, and path protection. The security is built into two main areas: middleware that adds protective headers to responses, and utility functions that validate user input.

## Security Architecture

The application uses a layered security approach:

1. **SecurityHeadersMiddleware** - Adds protective headers to all responses
2. **Input Validation Functions** - Validates and sanitizes user input
3. **Path Protection** - Prevents access to files outside the storage directory

## SecurityHeadersMiddleware

**Location**: `app/middleware/security_headers.py` (136 lines)

This middleware runs on every request and adds security headers to protect against common attacks.

### What It Does

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, debug: bool = False):
        super().__init__(app)
        self.debug = debug

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        self._add_security_headers(request, response)
        return response
```

### Security Headers Added

**Basic Protection** (applied to all pages):
```python
response.headers["X-Content-Type-Options"] = "nosniff"           # Prevents MIME sniffing attacks
response.headers["X-Frame-Options"] = "SAMEORIGIN"              # Prevents clickjacking
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"  # Controls referrer info
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"  # Forces HTTPS
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), fullscreen=(self)"  # Blocks unnecessary features
```

### Content Security Policy (CSP)

The middleware creates different security policies depending on what type of page is being served:

**API Endpoints** (`/api/*`):
- Very strict: blocks almost everything since APIs only need to return data
- `default-src 'none'` - blocks all content by default
- `frame-ancestors 'none'` - prevents embedding in other sites

**File Downloads** (`/api/artifacts/serve`):
- Allows some flexibility for archived HTML files
- Permits inline styles and scripts (needed for SingleFile HTML)
- Allows data URLs for embedded images and fonts
- Only allows embedding from same origin

**Documentation Pages** (`/docs`, `/redoc`):
- Allows CDN resources for Swagger UI to work
- Permits necessary scripts and styles from jsdelivr.net
- Allows FastAPI assets and web fonts

**Regular Web Pages**:
- Balanced policy that works with Tailwind CSS and Alpine.js
- Allows same-origin content and some external resources
- Permits WebSocket connections in debug mode

## Input Validation Functions

**Location**: `app/utils/security.py` (242 lines)

These functions check user input to prevent attacks and ensure data safety.

### Main Validation Functions

#### Snapshot ID Validation
```python
def validate_snapshot_id(snapshot_id: str, validation_config: ValidationConfig) -> str:
    """Makes sure snapshot IDs are safe and properly formatted."""
```

**What it checks:**
- Not empty
- Not too long (configurable limit)
- No path traversal attempts (`../`, `/`, `\`)
- No dangerous control characters
- Matches the expected pattern (regex)

**Example dangerous inputs it blocks:**
- `../../../etc/passwd`
- `req_test\..\..\windows\system32`
- Strings with null bytes or control characters

#### File Path Validation
```python
def validate_file_path(file_path: Path, storage_root: Path) -> Path:
    """Ensures files are within the allowed storage directory."""
```

**What it does:**
- Resolves the full file path (handles symlinks)
- Checks that the file is inside the storage directory
- Prevents access to files outside the archives folder

**Example attacks it prevents:**
- `/var/archives/../../../etc/passwd`
- Symlink attacks pointing outside storage

#### Artifact Type Validation
```python
def validate_artifact_type(artifact_type: str, validation_config: ValidationConfig) -> str:
    """Only allows known safe file types."""
```

**Allowed file types:**
- `archive.wacz` - Web archive files
- `metadata.json` - Snapshot metadata
- `screenshot.png` - Page screenshots
- `singlefile.html` - Archived HTML
- `warc.file` - Web archive format
- `document.html` - Document files

### Content Security Functions

#### Safe File Downloads
```python
def get_content_disposition(artifact_type: str, snapshot_id: str) -> str:
    """Creates safe download filenames and headers."""
```

**What it does:**
- Creates safe filenames by removing dangerous characters
- Sets `inline` for HTML files (so they display in browser)
- Sets `attachment` for other files (forces download)
- Prevents filename injection attacks

## Security Configuration

### Validation Settings

The security validation is configured in `app/config/models.py`:

```python
class ValidationConfig(BaseModel):
    # Snapshot ID rules
    snapshot_id_pattern: str = r'^req_[a-zA-Z0-9\-_]+_\d{8}_\d{6}$'
    snapshot_id_max_length: int = 100

    # File safety
    filename_max_length: int = 255
    allowed_artifact_types: Set[str] = {
        "archive.wacz", "metadata.json", "screenshot.png",
        "singlefile.html", "warc.file", "document.html"
    }

    # File type mappings
    content_type_mappings: Dict[str, str] = {
        "archive.wacz": "application/zip",
        "metadata.json": "application/json",
        "screenshot.png": "image/png",
        "singlefile.html": "text/html",
        "warc.file": "application/warc",
        "document.html": "text/html"
    }
```

### Environment Configuration

You can override security settings with environment variables:
- `CIVERS_VALIDATION_SNAPSHOT_ID_PATTERN` - Change the ID pattern
- `CIVERS_VALIDATION_SNAPSHOT_ID_MAX_LENGTH` - Change max ID length
- `CIVERS_VALIDATION_FILENAME_MAX_LENGTH` - Change max filename length

## How Security Integrates with the App

### Middleware Pipeline Order

The security middleware runs in a specific order:

```
1. CorrelationIdMiddleware (adds request ID)
2. SecurityHeadersMiddleware (adds protective headers)
3. ErrorDispatcherMiddleware (handles errors)
4. Your request reaches the actual endpoint
```

### Integration with FastAPI

The security middleware is added in `app/main.py`:

```python
# Add security middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    debug=os.getenv("DEBUG", "False").lower() == "true"
)
```

### Usage in API Endpoints

API endpoints use the validation functions:

```python
# In /api/artifacts/serve endpoint
validated_snapshot_id = validate_snapshot_id(snapshot_id, validation_config)
validated_artifact_type = validate_artifact_type(artifact_type, validation_config)
```

## Security Monitoring

### Logging Security Events

The validation functions log suspicious activity:

- **Warning level**: Path traversal attempts, dangerous characters
- **Info level**: Normal validation failures
- **Debug level**: Successful validations

Example log entry:
```json
{
  "level": "WARNING",
  "message": "Path traversal attempt detected: ../../../etc/passwd",
  "correlation_id": "req_123456",
  "client_ip": "192.168.1.100"
}
```

### Audit Trail

All security validations include:
- Request correlation ID for tracking
- Client IP address (when available)
- Exact input that was rejected
- Reason for rejection

## Testing Security

The security functions are designed to be easily testable:

```python
def test_path_traversal_blocked():
    """Test that path traversal attempts are blocked."""
    malicious_ids = [
        "../etc/passwd",
        "req_test_20230101_000000/../../../secret",
    ]

    for malicious_id in malicious_ids:
        with pytest.raises(SecurityValidationError):
            validate_snapshot_id(malicious_id, validation_config)
```

## Summary

The security system provides multiple layers of protection:

- **Headers**: Protect against XSS, clickjacking, and other browser-based attacks
- **Input Validation**: Block malicious input before it can cause damage
- **Path Protection**: Keep file access within safe boundaries
- **Monitoring**: Log security events for analysis
- **Configuration**: Flexible settings that can be adjusted for different environments

The approach focuses on preventing common web vulnerabilities while remaining practical for the archive browsing use case.