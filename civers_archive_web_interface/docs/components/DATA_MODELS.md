# Data Models Component Documentation

## Component Overview

The data models component serves as the core type-safe data layer for the Civers Archive Web Interface project. Built with Pydantic v2, these models provide:

- **Type-safe data validation** for all API requests and responses
- **Automatic OpenAPI documentation generation** for FastAPI endpoints
- **Data serialization/deserialization** between JSON and Python objects
- **Custom validation rules** for security and data integrity
- **Structured error handling** with detailed validation feedback
- **Consistent response formatting** across all API endpoints

The models act as the contract between the frontend, API layer, and storage system, ensuring data consistency throughout the application stack.

## File Structure and Model Distribution

| File | Lines | Models | Purpose |
|------|-------|---------|----------|
| `__init__.py` | 22 | 0 | Module exports and documentation |
| `url.py` | 157 | 1 | ArchivedUrl model for URL directories |
| `artifact.py` | 196 | 2 | Artifact and ArtifactType for files |
| `snapshot.py` | 252 | 1 | Snapshot model for timestamped captures |
| `snapshot_filters.py` | 236 | 3 | Filtering, sorting, and summary models |
| `responses.py` | 296 | 7 | API response formatting models |
| **Total** | **1,159** | **14** | Complete data model layer |

## Core Data Models

### 1. ArchivedUrl Model (`url.py`)

**Purpose**: Represents a URL directory in the storage structure with all its snapshots.

**Key Fields**:
```python
class ArchivedUrl(BaseModel):
    url_id: str = Field(..., min_length=1, max_length=255)
    original_url: HttpUrl = Field(...)
    folder_name: str = Field(..., min_length=1, max_length=255)
    snapshots: List[Snapshot] = Field(default_factory=list)
```

**Validation Rules**:
- **URL ID Security**: Only alphanumeric characters, underscores, and hyphens allowed
- **URL Normalization**: Automatically adds `https://` scheme if missing
- **Snapshot Sorting**: Automatically sorts snapshots by timestamp (newest first)

**Key Validators**:
```python
@field_validator('url_id')
@classmethod
def validate_url_id(cls, v):
    if not v.replace('_', '').replace('-', '').isalnum():
        raise ValueError('url_id must contain only alphanumeric characters, underscores, and hyphens')
    return v

@field_validator('original_url', mode='before')
@classmethod
def validate_original_url(cls, v):
    if isinstance(v, str) and not v.startswith(('http://', 'https://')):
        return f'https://{v}'
    return v
```

**Computed Properties**:
- `snapshot_count`: Number of snapshots
- `first_captured`/`last_captured`: Date range information
- `date_range`: Human-readable date span

### 2. Snapshot Model (`snapshot.py`)

**Purpose**: Represents a single timestamped capture of a URL.

**Key Fields**:
```python
class Snapshot(BaseModel):
    snapshot_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(...)
    url: HttpUrl = Field(...)
    title: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    available_artifacts: List[str] = Field(default_factory=list)
    artifacts: Optional[List[Artifact]] = Field(None)
```

**Validation Rules**:
- **Snapshot ID Format**: Supports both legacy (`YYYYMMDDTHHMMSSZ`) and new request format (`req_{id}_{timestamp}`)
- **Timestamp Parsing**: Handles multiple datetime formats (ISO, compact)
- **Artifact Type Validation**: Only allows predefined artifact types
- **Metadata Type Coercion**: Converts string status codes and content lengths to integers

**Key Validators**:
```python
@field_validator('snapshot_id')
@classmethod
def validate_snapshot_id_format(cls, v):
    if v.startswith('req_'):
        if len(v) < 10:
            raise ValueError('snapshot_id must be valid request format')
    else:
        if len(v) != 16:
            raise ValueError('snapshot_id must be 16 characters')
        try:
            datetime.strptime(v, '%Y%m%dT%H%M%SZ')
        except ValueError:
            raise ValueError('snapshot_id must be valid timestamp format')
    return v

@field_validator('available_artifacts')
@classmethod
def validate_artifact_types(cls, v):
    allowed_types = {
        'archive.wacz', 'metadata.json', 'screenshot.png',
        'singlefile.html', 'warc.file', 'document.html'
    }
    for artifact in v:
        if artifact not in allowed_types:
            raise ValueError(f'Invalid artifact type: {artifact}')
    return list(set(v))
```

**Computed Properties**:
```python
@property
def has_wacz(self) -> bool:
    return 'archive.wacz' in self.available_artifacts

@property
def formatted_timestamp(self) -> str:
    return self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')

@property
def status_code(self) -> Optional[int]:
    return self.metadata.get('status')
```

### 3. Artifact Model (`artifact.py`)

**Purpose**: Represents individual files within snapshots.

**Key Components**:
```python
class ArtifactType(str, Enum):
    WARC = "warc.file"
    SCREENSHOT = "screenshot.png"
    SINGLEFILE = "singlefile.html"
    DOCUMENT = "document.html"

class Artifact(BaseModel):
    artifact_type: ArtifactType = Field(...)
    filename: str = Field(..., min_length=1, max_length=255)
    file_path: Optional[str] = Field(None, exclude=True)
    size_bytes: Optional[int] = Field(None, ge=0)
    exists: bool = Field(True)
    mime_type: Optional[str] = Field(None)
    checksum: Optional[str] = Field(None, max_length=64)
```

**Security validation:**
```python
@field_validator('filename')
def validate_filename(cls, v):
    if '..' in v or '/' in v or '\\' in v:
        raise ValueError('filename cannot contain path traversal characters')
    return v
```

**Factory methods:**
```python
@classmethod
def create_from_file(cls, artifact_type: ArtifactType, file_path: Path) -> 'Artifact':
    exists = file_path.exists()
    size_bytes = file_path.stat().st_size if exists else None
    return cls(
        artifact_type=artifact_type,
        filename=file_path.name,
        file_path=str(file_path),
        size_bytes=size_bytes,
        exists=exists
    )
```

## Response Models and API Integration

### Structured Response System (`responses.py`)

The response models ensure consistent API output formatting:

**1. Error Response with Detailed Validation**:
```python
class ErrorDetail(BaseModel):
    field: Optional[str] = Field(None)
    message: str = Field(...)
    code: Optional[str] = Field(None)

class ErrorResponse(BaseModel):
    success: bool = Field(False)
    error: str = Field(...)
    message: str = Field(...)
    details: Optional[List[ErrorDetail]] = Field(None)
    request_id: Optional[str] = Field(None)
```

**2. Generic Paginated Response**:
```python
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = Field(True)
    data: List[T] = Field(...)
    pagination: PaginationMeta = Field(...)
```

**3. Pagination Metadata with Smart Calculation**:
```python
class PaginationMeta(BaseModel):
    @classmethod
    def create(cls, page: int, limit: int, total_count: int) -> 'PaginationMeta':
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0
        has_next = page < total_pages
        has_previous = page > 1
        return cls(
            page=page, limit=limit, total_count=total_count,
            total_pages=total_pages, has_next=has_next, has_previous=has_previous
        )
```

## Filtering and Sorting Models

### SnapshotFilters (`snapshot_filters.py`)

**Advanced Filtering Capabilities**:
```python
class SnapshotFilters(BaseModel):
    # Date range filtering
    from_date: Optional[datetime] = Field(None)
    to_date: Optional[datetime] = Field(None)

    # Artifact availability filtering
    has_wacz: Optional[bool] = Field(None)
    has_screenshot: Optional[bool] = Field(None)
    has_singlefile: Optional[bool] = Field(None)
    has_document: Optional[bool] = Field(None)

    # Status code filtering
    status_code: Optional[int] = Field(None, ge=100, le=599)
```

**Intelligent Date Parsing**:
```python
@field_validator('from_date', 'to_date', mode='before')
@classmethod
def parse_date(cls, v):
    if isinstance(v, str):
        formats = [
            '%Y-%m-%d',              # YYYY-MM-DD
            '%Y-%m-%dT%H:%M:%SZ',    # ISO with Z
            '%Y-%m-%dT%H:%M:%S',     # ISO without Z
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(v, fmt)
                if parsed.tzinfo is None:
                    from datetime import timezone
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                continue
        raise ValueError(f'Invalid date format: {v}')
    return v
```

## Validation Patterns

### Built-in Validators Used

1. **Field Constraints**:
   - `min_length`/`max_length` for string validation
   - `ge`/`le` for numeric ranges
   - `HttpUrl` for URL validation

2. **Pydantic Features**:
   - `Field(exclude=True)` to hide internal paths from API
   - `default_factory` for mutable defaults
   - `ConfigDict` for model configuration

### Custom Validators Implemented

1. **Security Validators**:
   ```python
   # Path traversal prevention
   @field_validator('filename')
   def validate_filename(cls, v):
       if '..' in v or '/' in v or '\\' in v:
           raise ValueError('filename cannot contain path traversal characters')

   # Filesystem-safe identifiers
   @field_validator('url_id')
   def validate_url_id(cls, v):
       if not v.replace('_', '').replace('-', '').isalnum():
           raise ValueError('url_id must contain only alphanumeric characters, underscores, and hyphens')
   ```

2. **Data Normalization Validators**:
   ```python
   # URL scheme normalization
   @field_validator('original_url', mode='before')
   def validate_original_url(cls, v):
       if isinstance(v, str) and not v.startswith(('http://', 'https://')):
           return f'https://{v}'

   # Automatic sorting
   @field_validator('snapshots')
   def sort_snapshots_by_timestamp(cls, v):
       if v:
           return sorted(v, key=lambda s: s.timestamp, reverse=True)
   ```

## Type Safety Implementation

### Strong Type Annotations

Every model uses comprehensive type hints:
```python
from typing import Dict, List, Optional, Any, Generic, TypeVar

# Generic type variables for reusable models
T = TypeVar('T')

# Complex type annotations
metadata: Dict[str, Any] = Field(default_factory=dict)
snapshots: List[Snapshot] = Field(default_factory=list)
artifacts: Optional[List[Artifact]] = Field(None)
```

### Enum-Based Constraints

```python
class ArtifactType(str, Enum):
    WARC = "warc.file"
    SCREENSHOT = "screenshot.png"
    SINGLEFILE = "singlefile.html"
    DOCUMENT = "document.html"

class SnapshotSortOption(str, Enum):
    TIMESTAMP_DESC = "timestamp"
    TIMESTAMP_ASC = "timestamp_asc"
    TITLE = "title"
    STATUS_CODE = "status_code"
```

## Model Relationships and Dependencies

### Hierarchical Structure

```
ArchivedUrl
├── snapshots: List[Snapshot]
    ├── artifacts: Optional[List[Artifact]]
    └── available_artifacts: List[str]

Filtering Layer
├── SnapshotFilters (query parameters)
├── SnapshotSummary (lightweight responses)
└── SnapshotSortOption (ordering)

Response Layer
├── PaginatedResponse[T] (generic wrapper)
├── ErrorResponse (error handling)
└── PaginationMeta (metadata)
```

## Serialization/Deserialization Patterns

### JSON Schema Generation

Models automatically generate OpenAPI-compatible schemas:
```python
# Serialization with exclusions
json_data = snapshot.model_dump(exclude={'folder_path', 'file_path'})

# JSON string generation
json_str = snapshot.model_dump_json()

# Schema extraction
schema = snapshot.model_json_schema()
```

## Configuration and Settings

### Model Configuration

```python
model_config = ConfigDict(
    use_enum_values=True,      # Serialize enums as values
    json_schema_extra={        # OpenAPI examples
        "example": {...}
    }
)
```

### Field Configuration

```python
# Exclude internal fields from API
file_path: Optional[str] = Field(None, exclude=True)

# Validation constraints
status_code: Optional[int] = Field(None, ge=100, le=599)

# Rich descriptions for OpenAPI
url_id: str = Field(
    ...,
    description="Filesystem-safe identifier for the URL",
    min_length=1,
    max_length=255
)
```

## Integration with API Layer

The models are extensively used throughout the API layer:

- **URL Endpoints** (`api/urls.py`): ArchivedUrl, Snapshot, SnapshotFilters, PaginatedResponse
- **Snapshot Details** (`api/snapshot_detail.py`): Snapshot, ErrorResponse
- **Artifact Serving** (`api/artifacts.py`): ErrorResponse
- **Storage Layer** (`storage/`): All models for data conversion
- **Error Handling**: ErrorResponse and ErrorDetail for validation failures

## Summary

The Civers Web Interface data models provide a robust, type-safe foundation with:

- **14 Pydantic models** across 6 files totaling 1,159 lines
- **Comprehensive validation** including security, format, and business rules
- **Flexible filtering and sorting** capabilities
- **Consistent API response formatting**
- **Strong type safety** with generic support
- **Extensive test coverage** with 95+ test cases
- **Integration patterns** for storage layer conversion
- **Performance optimization** through lightweight summary models

The models successfully abstract the complexity of the storage layer while providing a clean, validated interface for the API layer and ensuring data integrity throughout the application.