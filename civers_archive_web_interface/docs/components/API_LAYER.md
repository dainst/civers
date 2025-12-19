# API Layer Documentation

## Overview

The API layer provides REST endpoints for browsing and serving archived website snapshots. It uses FastAPI with modular routers and includes security validation, error handling, and response formatting.

**What it does:**
- Security-first input validation and path traversal protection
- Standardized response formats for success and errors
- Built-in pagination for large datasets
- Direct integration with storage service
- Detailed error responses with proper HTTP status codes

## Files

| File | Lines | Endpoints | Purpose |
|------|-------|-----------|---------|
| `artifacts.py` | 135 | 1 | Serves files (WACZ, screenshots, etc.) |
| `urls.py` | 262 | 2 | Lists URLs and snapshots with filtering |
| `snapshot_detail.py` | 163 | 1 | Shows individual snapshot details |
| **Total** | **560** | **4** | **Complete API** |

## API Endpoints

### 1. File Serving (`artifacts.py`)

**`GET /api/artifacts/serve`**
- **What it does**: Securely serves artifact files (WACZ, screenshots, metadata, etc.)
- **Parameters**:
  - `snapshot_id` (required): Snapshot identifier
  - `type` (required): Artifact type (archive.wacz, screenshot.png, etc.)

**Response:**
```python
# Returns FileResponse with security headers
- Content-Type: Based on artifact type
- Content-Disposition: inline for HTML, attachment for others
- X-Content-Type-Options: nosniff
- Cache-Control: private, max-age=3600
```

**Security:**
- Input validation against patterns
- Path traversal protection
- File existence checks
- Storage boundary validation
- Access logging with client IP

### 2. URL Listing (`urls.py`)

**`GET /api/urls`**
- **What it does**: Paginated list of all archived URLs with sorting
- **Parameters**:
  - `page` (default: 1): Page number
  - `limit` (default: 50, max: 100): Items per page
  - `sort` (default: "url"): Sort by url, last_captured, or snapshot_count

**`GET /api/urls/{url_id}/snapshots`**
- **What it does**: Paginated snapshots for a specific URL with filtering
- **Parameters**:
  - `url_id` (path): URL identifier
  - `page`, `limit`: Pagination
  - `sort`: timestamp, timestamp_asc, title, status_code
  - `from_date`, `to_date`: Date range (YYYY-MM-DD)
  - `has_wacz`, `has_screenshot`, `has_singlefile`, `has_document`: Boolean filters
  - `status_code`: HTTP status filter (100-599)

### 3. Snapshot Details (`snapshot_detail.py`)

**`GET /api/snapshots/{snapshot_id}`**
- **What it does**: Complete details for a single snapshot
- **Parameters**: `snapshot_id` (path): Snapshot identifier

**Response:**
```python
class SnapshotDetail(BaseModel):
    snapshot_id: str
    timestamp: str  # ISO format
    readable_timestamp: str
    original_url: str
    title: Optional[str]
    artifacts: Dict[str, ArtifactInfo]  # Available artifacts
    metadata: Dict[str, Any]  # Complete metadata
    artifact_count: int
    has_replay_content: bool
    status_code: Optional[int]
    content_type: Optional[str]
    content_length: Optional[int]
```

## How It Works

### Router Pattern

Each API module uses FastAPI routers:

```python
from fastapi import APIRouter
router = APIRouter(prefix="/api", tags=["ModuleName"])

@router.get("/endpoint")
async def endpoint_function(request: Request, ...):
    # Implementation
```

### Storage Integration

All endpoints access storage through app state:

```python
async def endpoint(request: Request, ...):
    # Get storage service
    storage_service = request.app.state.storage_service

    # Use storage methods
    archived_url = storage_service.get_url_by_id(url_id)
    snapshot = storage_service.get_snapshot_by_id(snapshot_id)
```

## Pagination and Filtering

### Pagination

All list endpoints use consistent pagination:

```python
# Calculate pagination bounds
total_count = len(filtered_data)
start_idx = (page - 1) * limit
end_idx = start_idx + limit

# Validate page bounds
if page > 1 and start_idx >= total_count:
    total_pages = math.ceil(total_count / limit)
    raise ValidationError(f"Page {page} does not exist. Total pages: {total_pages}")

# Create pagination metadata
pagination = PaginationMeta.create(page=page, limit=limit, total_count=total_count)
```

### Filtering

The snapshot filtering system supports:
- **Date Ranges**: Flexible date parsing (YYYY-MM-DD, ISO format)
- **Artifact Filters**: Boolean filters for different artifact types
- **HTTP Status**: Numeric filtering (100-599 range)
- **Timezone Handling**: Timezone-aware date comparisons

```python
class SnapshotFilters(BaseModel):
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    has_wacz: Optional[bool] = None
    has_screenshot: Optional[bool] = None
    # ... other filters

    def applies_to_snapshot(self, snapshot) -> bool:
        # Filtering logic with timezone awareness
```

## Error Handling

### Custom Exceptions

```python
class ResourceNotFoundError(Exception):
    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id

class ArtifactNotFoundError(Exception):
    def __init__(self, artifact_type: str, snapshot_id: str):
        self.artifact_type = artifact_type
        self.snapshot_id = snapshot_id

class ValidationError(Exception):
    def __init__(self, message: str, field: str = None):
        self.field = field
```

### Error Response Types

- **400 Bad Request**: Validation errors with field details
- **404 Not Found**: Resource-specific error messages
- **500 Internal Server Error**: Generic server errors

## Security and Validation

### Input Validation

```python
def validate_snapshot_id(snapshot_id: str, validation_config: ValidationConfig) -> str:
    # Length limits, pattern matching, path traversal protection

def validate_artifact_type(artifact_type: str, validation_config: ValidationConfig) -> str:
    # Whitelist validation, dangerous character detection

def validate_file_path(file_path: Path, storage_root: Path) -> Path:
    # Storage boundary validation, symlink resolution
```

**Security Features:**
- **Path Traversal Protection**: Prevents `../` attacks
- **Input Sanitization**: Character filtering and length limits
- **Whitelist Validation**: Only allowed artifact types
- **Storage Boundary Checks**: Files must be within storage directory
- **Audit Logging**: Access attempts logged with client IP

## Integration

Routers are integrated in `main.py`:

```python
# Import routers
from .api.urls import router as urls_router
from .api.snapshot_detail import router as snapshots_router
from .api.artifacts import router as artifacts_router

# Include in application
app.include_router(urls_router)      # /api/urls, /api/urls/{url_id}/snapshots
app.include_router(snapshots_router) # /api/snapshots/{snapshot_id}
app.include_router(artifacts_router) # /api/artifacts/serve
```

**Application Setup:**
- Configuration loaded at startup
- Storage service attached to app.state
- Global error handlers registered

## Testing

API endpoints are designed for testing:
- **Dependency Injection**: Storage service mockable via app.state
- **Response Models**: Pydantic models ensure response validation
- **Error Scenarios**: Custom exceptions enable precise error testing
- **Security Testing**: Input validation functions unit testable
- **Integration Testing**: Full request/response cycle testable

## Summary

The API layer provides a secure REST interface for browsing archived web content. With 4 endpoints across 560 lines of code, it delivers:

- Paginated browsing of URLs and snapshots
- Detailed metadata access
- Secure file serving
- Input validation and error handling
- Filtering and sorting capabilities