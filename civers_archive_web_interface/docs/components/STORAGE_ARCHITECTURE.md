# Storage Architecture Documentation

## Overview

The storage system handles archived web content using a provider pattern. This lets you switch between different storage backends (filesystem, S3, database) without changing the API code. It includes caching for better performance and integrates cleanly with FastAPI.

**What it does**: Manages archived URLs, snapshots, and artifacts with caching and provider switching

**How it works**: Acts as the interface between API endpoints and storage backends

## Files

```
app/storage/
├── service.py                     (270 lines) - Main service with caching
├── factory.py                     (106 lines) - Creates providers and services
└── providers/
    ├── storage_provider_interface.py (136 lines) - Interface for all providers
    └── filesystem.py              (496 lines) - Filesystem implementation
```

**Total**: 1,043 lines across 6 files

## Main Components

### StorageService (service.py)

**The main interface that adds caching and business logic on top of storage providers.**

```python
class StorageService:
    def __init__(self, provider: StorageProviderInterface, cache_ttl_seconds: int = 60):
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_urls: Optional[Dict[str, ArchivedUrl]] = None
        self._cache_timestamp = 0.0
```

**Main methods:**

```python
def get_all_urls(self) -> Dict[str, ArchivedUrl]:
    # Returns all archived URLs, using cache if available
    if self._cached_urls is None or self._is_cache_expired():
        return self._refresh_cache()
    return self._cached_urls

def get_url_by_id(self, url_id: str) -> Optional[ArchivedUrl]:
    # Get specific URL by ID from cache
    all_urls = self.get_all_urls()
    return all_urls.get(url_id)

def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
    # Get specific snapshot (goes directly to provider)
    return self.provider.get_snapshot_by_id(snapshot_id)

def get_artifact_stream(self, snapshot_id: str, artifact_type: str) -> Optional[IO]:
    # Get file stream for artifacts (WACZ, screenshots, etc.)
    return self.provider.get_artifact_stream(snapshot_id, artifact_type)
```

### StorageProviderInterface (storage_provider_interface.py)

**The interface that all storage providers must implement.**

```python
class StorageProviderInterface(ABC):
    @abstractmethod
    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        # Get all archived URLs from storage backend
        pass

    @abstractmethod
    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        # Get specific snapshot by ID
        pass

    @abstractmethod
    def get_artifact_stream(self, snapshot_id: str, artifact_type: str) -> Optional[IO]:
        # Get file stream for artifacts
        pass
```

### FilesystemStorageProvider (filesystem.py)

**The filesystem implementation that reads archives from local directories.**

```python
class FilesystemStorageProvider(StorageProviderInterface):
    def __init__(self, storage_path: Path, timeout_seconds: int = 10, validation_config: ValidationConfig = None):
        self.storage_path = Path(storage_path)
        self.timeout_seconds = timeout_seconds
        self.validation_config = validation_config or ValidationConfig()
```

**What it does:**
- Scans directory structure: `archives/domain/path_segment/req_request-id_timestamp/`
- Parses JSON metadata files
- Has timeout protection for large directory scans
- Finds available artifacts (WACZ files, screenshots, etc.)

## Design Patterns

### 1. Provider Pattern
- **Interface**: `StorageProviderInterface` defines what all providers must do
- **Implementations**: `FilesystemStorageProvider` (can add S3, database providers later)
- **Benefits**: Easy to switch backends, test with mocks, add new storage types

### 2. Service Layer
- **Service**: `StorageService` adds caching and business logic
- **Purpose**: Hides provider complexity from API endpoints
- **Handles**: Caching, error handling, business rules

### 3. Factory Pattern
- **Factory**: Creates providers and services based on configuration
- **Benefits**: Centralized creation logic, configuration-driven setup
- **Integration**: Works with FastAPI dependency injection

## FastAPI Integration

**Setup at startup:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load configuration
    app_config = load_app_config()
    app.state.app_config = app_config

    # Create storage service
    storage_service = create_storage_service(app_config)
    app.state.storage_service = storage_service
```

**Use in API endpoints:**
```python
@router.get("/api/urls")
async def list_urls(request: Request, page: int = 1, limit: int = 20):
    # Get storage service from app state
    storage_service = request.app.state.storage_service

    # Use service methods
    all_urls = storage_service.get_all_urls()
```

## Caching

**How caching works:**
- **Where**: Service layer caches all URLs together
- **TTL**: Configurable time-to-live (default: 60 seconds)
- **Invalidation**: Expires based on time

**Cache logic:**
```python
def _is_cache_expired(self) -> bool:
    if self.cache_ttl_seconds <= 0:
        return True  # Caching disabled
    return time.time() - self._cache_timestamp > self.cache_ttl_seconds
```

## Error Handling

**Exception types:**
```
StorageError (base)
├── StorageTimeoutError (operation timeouts)
└── StoragePermissionError (access denied)
```

**How errors are handled:**
- **Provider Level**: Catch filesystem errors, convert to StorageError
- **Service Level**: Add context and logging
- **API Level**: Convert to HTTP error responses
- **Graceful Degradation**: Continue when possible on partial failures

## Adding New Storage Providers

**Step 1: Implement the interface**
```python
class S3StorageProvider(StorageProviderInterface):
    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str):
        # S3 client setup

    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        # S3 bucket scanning logic
```

**Step 2: Update the factory**
```python
def create_storage_provider(app_config: AppConfig) -> StorageProviderInterface:
    config = app_config.storage
    if config.type == 'filesystem':
        return _create_filesystem_provider(config, app_config.validation)
    elif config.type == 's3':
        return _create_s3_provider(config)
```

## Summary

The storage system has a clean, layered design:

1. **Provider Layer**: Pluggable backend implementations
2. **Service Layer**: Business logic and caching
3. **Factory Layer**: Configuration-driven creation
4. **Integration Layer**: FastAPI dependency injection

The design focuses on performance through caching, maintainability through clean abstractions, and extensibility through the provider pattern. The filesystem implementation handles errors well, has timeout protection, and parses metadata reliably.