# Error Handling Architecture

## Components

**Exception Handlers** → FastAPI's exception handling system
- Catches validation errors before middleware execution
- Located: `app/custom_exceptions/handlers.py`

**ErrorDispatcherMiddleware** → Catches runtime errors during route execution
- Routes to `APIErrorHandler` (JSON) or `PageErrorHandler` (HTML)
- Located: `app/middleware/error_handlers/`

## Execution Flow

```
Request → FastAPI Validation → Middleware → Route Handler
    ↓ (422 errors)        ↓ (404, 500, business errors)
Exception Handlers    ErrorDispatcherMiddleware
```

## When Each Is Invoked

### Exception Handlers (Pre-Middleware)
**Triggers**: FastAPI parameter validation failures

**Examples**:
```bash
GET /api/artifacts/serve                    # Missing required parameters
GET /api/artifacts/serve?snapshot_id=       # Empty required parameter
```

**Response**: 422 with field-level validation details

### Middleware Handlers (Runtime)
**Triggers**: Route execution errors

**Examples**:
```bash
GET /api/unknown-endpoint                   # Route not found (404)
GET /api/snapshots/valid-id                 # Business logic error (500)
```

**Response**: 404/500 with error message

## Key Difference

- **Exception Handlers**: Parameter validation (before route runs)
- **Middleware Handlers**: Business logic errors (during/after route runs)

Both use the same error formatting for consistent API responses.