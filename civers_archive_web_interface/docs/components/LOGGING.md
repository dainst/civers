# Logging System Component Documentation

## Component Overview

The Civers Web Interface implements a sophisticated structured logging system built around the `asgi-correlation-id` middleware pattern. This logging architecture provides comprehensive observability, request tracing, and debugging capabilities through JSON-formatted structured logs with automatic correlation ID tracking.

### Core Philosophy
- **Structured Logging**: All logs are formatted as JSON objects with consistent fields for machine readability
- **Request Correlation**: Every request gets a unique correlation ID that tracks through the entire request lifecycle
- **Security-First**: Sensitive data is automatically filtered from log outputs
- **Environment-Aware**: Different configurations for development and production environments
- **Centralized Configuration**: Single point of configuration for all logging behavior

## File Structure

```
app/logging/
├── __init__.py          (8 lines)   - Module exports and interface
├── config.py           (69 lines)   - Logging configuration and setup
└── formatters.py       (82 lines)   - Custom JSON formatter with correlation ID
```

**Total Lines of Code**: 159 lines

### Component Descriptions

- **`__init__.py`**: Provides clean module interface, exports `configure_logging` function and `JSONFormatter` class
- **`config.py`**: Contains the main logging configuration using Python's `dictConfig` pattern with asgi-correlation-id integration
- **`formatters.py`**: Implements custom `JSONFormatter` class with automatic sensitive data filtering and correlation ID injection

## Logging Configuration

### Environment-Based Configuration

The logging system is configured at application startup in `app/main.py`:

```python
# Logging configuration from environment variables
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", None)
json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"

# Configure logging at startup
configure_logging(level=log_level, json_format=json_logging, log_file=log_file)
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOG_LEVEL` | `"INFO"` | Controls logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `JSON_LOGGING` | `"true"` | Enables/disables JSON formatting (true/false) |
| `LOG_FILE` | `None` | Optional file path for file-based logging |

### Log Level Management

The configuration supports different log levels for various components:

```python
'loggers': {
    # Application loggers
    'app': {'level': level.upper()},
    # Third-party loggers (reduced verbosity)
    'uvicorn': {'level': 'WARNING'},
    'uvicorn.access': {'level': 'WARNING'},
    'httpx': {'level': 'INFO'},
    'asgi_correlation_id': {'level': 'WARNING'},
}
```

### Output Destination Configuration

The system supports both console and file logging:

```python
'handlers': {
    'console': {
        'class': 'logging.StreamHandler',
        'filters': ['correlation_id'],
        'formatter': 'json' if json_format else 'console',
    },
    # File handler added conditionally
    'file': {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': log_file,
        'maxBytes': 10*1024*1024,  # 10MB
        'backupCount': 5,
        'filters': ['correlation_id'],
        'formatter': 'json' if json_format else 'console',
    }
}
```

### JSON vs Text Formatting

Two formatter options are available:

1. **JSON Formatter** (default): Structured JSON output for machine processing
2. **Console Formatter**: Human-readable text format for development

```python
'formatters': {
    'json': {'()': 'app.logging.formatters.JSONFormatter'},
    'console': {
        'format': '%(levelname)s: %(name)s [%(correlation_id)s] %(message)s',
        'datefmt': '%H:%M:%S',
    },
}
```

## Custom Formatters

### JSON Formatter Implementation

The `JSONFormatter` class (`app/logging/formatters.py`) provides sophisticated structured logging:

```python
class JSONFormatter(logging.Formatter):
    """
    JSON formatter that includes correlation ID from asgi-correlation-id.

    Automatically filters sensitive data and includes correlation ID in all log entries.
    """

    # Sensitive field patterns for data filtering
    SENSITIVE_FIELDS = {
        'password', 'token', 'secret', 'key', 'authorization',
        'cookie', 'session', 'csrf', 'api_key', 'private'
    }
```

### Core Log Entry Structure

Every JSON log entry contains these standard fields:

```python
log_entry = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'level': record.levelname,
    'logger': record.name,
    'message': record.getMessage(),
    'correlation_id': correlation_id.get('not_set_yet'),
}
```

### Correlation ID Integration

The formatter automatically injects correlation IDs from the `asgi-correlation-id` context:

```python
from asgi_correlation_id.context import correlation_id

# In format method
'correlation_id': correlation_id.get('not_set_yet'),
```

### Sensitive Data Filtering

The formatter implements recursive filtering to protect sensitive information:

```python
def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively filter sensitive data from log entry.

    Returns:
        Dictionary with sensitive values replaced by '[FILTERED]'
    """
    # Check if key contains sensitive terms
    if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
        filtered[key] = '[FILTERED]'
```

### Debug-Level Enhancements

For debug-level logs, additional context is included:

```python
# Add file and line info for debug level
if record.levelno <= logging.DEBUG:
    log_entry['file'] = record.filename
    log_entry['line'] = record.lineno
    log_entry['function'] = record.funcName
```

## Integration Patterns

### FastAPI Application Integration

The logging system is integrated at the application level in the main FastAPI app:

```python
from .logging import configure_logging

# Configure logging before application startup
configure_logging(level=log_level, json_format=json_logging, log_file=log_file)

# Middleware stack (order matters - correlation ID is outermost)
app.add_middleware(ErrorDispatcherMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)  # Outermost for request tracing
```

### Middleware Integration with asgi-correlation-id

The `CorrelationIdMiddleware` is positioned as the outermost middleware to ensure correlation IDs are available throughout the request lifecycle:

```python
from asgi_correlation_id import CorrelationIdMiddleware

app.add_middleware(CorrelationIdMiddleware)
```

### Request Tracing and Correlation

Error handlers demonstrate proper correlation ID usage:

```python
from asgi_correlation_id.context import correlation_id

def _get_correlation_id() -> str:
    """Get correlation ID from asgi-correlation-id context."""
    return correlation_id.get('unknown')

# Usage in error responses
request_id = _get_correlation_id()
response.headers["X-Request-ID"] = request_id
```

### Logger Usage Patterns

Standard logger usage throughout the application:

```python
import logging

logger = logging.getLogger(__name__)

# Examples from routes/pages.py
logger.debug(f"Rendering archive page for URL ID: {url_id}")
logger.warning(f"URL ID not found: {url_id}")
logger.error(f"Error getting snapshot: {e}")
```

## Log Output Examples

### JSON Formatted Logs

Example JSON log entry structure:

```json
{
    "timestamp": "2024-09-25T13:23:45.123456+00:00",
    "level": "INFO",
    "logger": "app.routes.pages",
    "message": "Rendering archive page for URL ID: abc123",
    "correlation_id": "req_1727267025_abc123def456",
    "extra_field": "value"
}
```

### Error Log with Exception Info

```json
{
    "timestamp": "2024-09-25T13:23:45.123456+00:00",
    "level": "ERROR",
    "logger": "app.middleware.error_handlers.api_error_handler",
    "message": "API unhandled exception: Connection timeout",
    "correlation_id": "req_1727267025_xyz789",
    "error_type": "api_ConnectionTimeoutError",
    "path": "/api/snapshots/123",
    "exception": "Traceback (most recent call last):\n..."
}
```

### Debug Log with File Information

```json
{
    "timestamp": "2024-09-25T13:23:45.123456+00:00",
    "level": "DEBUG",
    "logger": "app.storage.service",
    "message": "Cache hit for snapshot abc123",
    "correlation_id": "req_1727267025_debug123",
    "file": "service.py",
    "line": 45,
    "function": "get_snapshot"
}
```

### Correlation ID Tracking Example

Request flow with consistent correlation ID:

```json
// Request start
{"level": "INFO", "correlation_id": "req_abc123", "message": "Processing GET /api/snapshots/456"}

// During processing
{"level": "DEBUG", "correlation_id": "req_abc123", "message": "Fetching snapshot from storage"}

// Error occurred
{"level": "ERROR", "correlation_id": "req_abc123", "message": "Storage operation failed"}

// Response
{"level": "INFO", "correlation_id": "req_abc123", "message": "Request completed with status 500"}
```

### Structured Data Examples

Logs with extra structured data:

```python
# From API error handler
logger.warning("API endpoint not found", extra={
    'status_code': 404,
    'error_type': 'api_not_found',
    'path': request.url.path
})
```

Results in:

```json
{
    "timestamp": "2024-09-25T13:23:45.123456+00:00",
    "level": "WARNING",
    "logger": "app.middleware.error_handlers.api_error_handler",
    "message": "API endpoint not found",
    "correlation_id": "req_1727267025_notfound",
    "status_code": 404,
    "error_type": "api_not_found",
    "path": "/api/nonexistent"
}
```

## Environment Configuration

### Development vs Production Logging

**Development Environment** (`docker-compose.yml`):
```yaml
environment:
  - LOG_LEVEL=DEBUG
  - JSON_LOGGING=true
```

**Production Environment**:
```yaml
environment:
  - LOG_LEVEL=INFO
  - JSON_LOGGING=true
```

### Environment Variable Configuration

The system uses environment variables for flexible configuration:

```bash
# Example .env configuration
LOG_LEVEL=info
JSON_LOGGING=true
LOG_FILE=/var/log/civers/app.log
DEBUG=false
```

### Log File Management

File logging with rotation is supported:

```python
config['handlers']['file'] = {
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': log_file,
    'maxBytes': 10*1024*1024,  # 10MB
    'backupCount': 5,  # Keep 5 backup files
    'filters': ['correlation_id'],
    'formatter': 'json' if json_format else 'console',
}
```

This creates:
- `app.log` (current log file)
- `app.log.1` through `app.log.5` (rotated backups)

## Testing Patterns for Logging

While no specific test files were found in the current analysis, the logging system supports testability through:

### Configuration Testing
```python
# Test different log levels
configure_logging(level="DEBUG", json_format=True)
configure_logging(level="ERROR", json_format=False)
```

### Formatter Testing
```python
# Test JSON formatter
formatter = JSONFormatter()
record = logging.LogRecord(
    name="test.logger",
    level=logging.INFO,
    pathname="test.py",
    lineno=10,
    msg="Test message",
    args=(),
    exc_info=None
)
```

### Correlation ID Testing
```python
# Test correlation ID integration
from asgi_correlation_id.context import correlation_id
# Mock correlation ID context for testing
```

## Key Features and Benefits

1. **Request Traceability**: Every log entry includes a correlation ID for end-to-end request tracking
2. **Security**: Automatic filtering of sensitive data from logs
3. **Structured Data**: JSON format enables efficient log parsing and analysis
4. **Environment Flexibility**: Easy configuration switching between development and production
5. **Performance**: Efficient logging with configurable levels and optional file output
6. **Integration**: Seamless FastAPI and middleware integration
7. **Observability**: Rich context information for debugging and monitoring
8. **Scalability**: Rotating file logs prevent disk space issues

## Summary

The logging system provides a robust foundation for observability and debugging in the Civers Web Interface, enabling efficient troubleshooting and monitoring of the application's behavior across different environments.