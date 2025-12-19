# Configuration Documentation

## Overview

The configuration system uses Pydantic models with environment variable overrides and YAML file support. It provides centralized configuration management with dependency injection throughout the application.

**Key features:**
- Type safety through Pydantic models with validation
- Environment variables override YAML configuration
- Single configuration entry point for the application
- Configuration injected into FastAPI application state
- Built-in validation with descriptive error messages
- Designed for future storage backends (S3, Database)

## Files

```
app/config/
├── loader.py            (128 lines)  - Configuration loading logic
└── models.py            (165 lines)  - Pydantic configuration models
```

**Configuration Models**: 5 main models (AppConfig, StorageConfig, FilesystemConfig, CacheConfig, ValidationConfig)

## Configuration Models

### 1. FilesystemConfig (`models.py`)

**What it configures**: Local filesystem storage provider settings.

**Fields:**
- `path: str` - Directory path for archives (default: "archives")
- `timeout_seconds: int` - Filesystem operation timeout (default: 10, must be ≥ 0)

**Validation:**
- Timeout must be non-negative
- Custom validator prevents negative timeout values

**Environment variables:**
- `CIVERS_FILESYSTEM_PATH` → `path`
- `CIVERS_FILESYSTEM_TIMEOUT_SECONDS` → `timeout_seconds`

**Code:**
```python
class FilesystemConfig(BaseModel):
    path: str = Field(default="archives", description="Path to archives directory")
    timeout_seconds: int = Field(default=10, ge=0, description="Filesystem operation timeout")

    @field_validator('timeout_seconds')
    def validate_timeout(cls, v):
        if v < 0:
            raise ValueError("timeout_seconds must be non-negative")
        return v
```

### 2. CacheConfig (`models.py`)

**What it configures**: Application-wide caching behavior.

**Fields:**
- `ttl_seconds: int` - Cache TTL in seconds (default: 60, -1 for no expiration)
- `max_entries: int` - Maximum cache entries (default: 1000, must be ≥ 1)

**Validation:**
- TTL must be -1 (no expiration) or positive (not 0)
- Max entries must be positive

**Environment variables:**
- `CIVERS_CACHE_TTL_SECONDS` → `ttl_seconds`

**Code:**
```python
class CacheConfig(BaseModel):
    ttl_seconds: int = Field(default=60, ge=1, description="Cache TTL in seconds (-1 for no expiration)")
    max_entries: int = Field(default=1000, ge=1, description="Maximum cache entries")

    @field_validator('ttl_seconds')
    def validate_ttl(cls, v):
        if v < -1 or v == 0:
            raise ValueError("ttl_seconds must be -1 (no expiration) or positive")
        return v
```

### 3. StorageConfig (`models.py`)

**What it configures**: Top-level storage configuration with provider selection and caching.

**Fields:**
- `type: Literal["filesystem"]` - Storage provider type (currently only filesystem)
- `filesystem: Optional[FilesystemConfig]` - Filesystem provider configuration
- `cache: CacheConfig` - Cache configuration (auto-created with defaults)

**Validation:**
- Model validator automatically creates filesystem config when type is "filesystem"
- Future support planned for S3 and database providers

**Environment variables:**
- `CIVERS_STORAGE_TYPE` → `type`

**Code:**
```python
class StorageConfig(BaseModel):
    type: Literal["filesystem",] = Field(default="filesystem")
    filesystem: Optional[FilesystemConfig] = None
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @model_validator(mode='before')
    def validate_storage_config(cls, data):
        if isinstance(data, dict):
            storage_type = data.get('type', 'filesystem')

            # Set default filesystem config if type is filesystem and no config provided
            if storage_type == 'filesystem' and 'filesystem' not in data:
                data['filesystem'] = {}

        return data
```

### 4. ValidationConfig (`models.py`)

**What it configures**: Input validation and security configuration.

**Fields:**
- `snapshot_id_pattern: str` - Regex pattern for snapshot ID validation
- `snapshot_id_max_length: int` - Maximum snapshot ID length (default: 100)
- `snapshot_directory_prefix: str` - Directory prefix for snapshots (default: "req_")
- `timestamp_formats: List[str]` - Supported timestamp formats
- `filename_max_length: int` - Maximum filename length (default: 255)
- `allowed_artifact_types: Set[str]` - Whitelisted artifact file types
- `content_type_mappings: Dict[str, str]` - MIME type mappings for artifacts

**Validation:**
- Length limits must be positive
- At least one timestamp format required
- Artifact type security whitelist

**Environment variables:**
- `CIVERS_VALIDATION_SNAPSHOT_ID_PATTERN` → `snapshot_id_pattern`
- `CIVERS_VALIDATION_SNAPSHOT_ID_MAX_LENGTH` → `snapshot_id_max_length`
- `CIVERS_VALIDATION_SNAPSHOT_DIRECTORY_PREFIX` → `snapshot_directory_prefix`
- `CIVERS_VALIDATION_FILENAME_MAX_LENGTH` → `filename_max_length`

### 5. AppConfig (`models.py`)

**What it configures**: Top-level application configuration container.

**Fields:**
- `storage: StorageConfig` - Storage configuration (auto-created with defaults)
- `validation: ValidationConfig` - Validation configuration (auto-created with defaults)

**Features:**
- `validate_assignment=True` for runtime validation
- Automatic factory creation of nested configurations

**Code:**
```python
class AppConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    storage: StorageConfig = Field(default_factory=StorageConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
```

## Configuration Loading

### Loading process (`loader.py`):

1. **YAML File Loading**: Loads from `config/storage.yaml` (default) or specified path
2. **Environment Variable Override**: Applies `CIVERS_*` environment variables
3. **Pydantic Validation**: Creates typed configuration objects with validation
4. **Error Handling**: Provides descriptive errors for configuration issues

**Main function:**
```python
def load_app_config(config_path: Optional[Path] = None) -> AppConfig:
    # Load configuration from YAML file with environment variable overrides
    # Returns: AppConfig instance with validated configuration
    # Raises: ConfigurationError if loading or validation fails
```

### Environment Variable Overrides

Environment variables follow the pattern `CIVERS_<SECTION>_<KEY>`:

**Storage overrides:**
- `CIVERS_STORAGE_TYPE` - Storage provider type
- `CIVERS_FILESYSTEM_PATH` - Filesystem storage path
- `CIVERS_FILESYSTEM_TIMEOUT_SECONDS` - Filesystem operation timeout
- `CIVERS_CACHE_TTL_SECONDS` - Cache TTL

**Validation overrides:**
- `CIVERS_VALIDATION_SNAPSHOT_ID_PATTERN` - Snapshot ID validation pattern
- `CIVERS_VALIDATION_SNAPSHOT_ID_MAX_LENGTH` - Maximum snapshot ID length
- `CIVERS_VALIDATION_SNAPSHOT_DIRECTORY_PREFIX` - Snapshot directory prefix
- `CIVERS_VALIDATION_FILENAME_MAX_LENGTH` - Maximum filename length

## FastAPI Integration

### Application startup (`main.py`):

Configuration is loaded during startup and injected into FastAPI application state:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Load application configuration
        app_config = load_app_config()
        app.state.app_config = app_config

        # Create storage service with configuration
        storage_service = create_storage_service(app_config)
        app.state.storage_service = storage_service

        logger.debug("Application initialized successfully")
    except ConfigurationError as e:
        logger.error(f"Failed to initialize application: {e}")
        raise RuntimeError(f"Application initialization failed: {e}") from e

    yield

    # Shutdown
    logger.debug("Application shutting down")
```

### Storage factory integration (`storage/factory.py`):

```python
def create_storage_provider(app_config: AppConfig) -> StorageProviderInterface:
    try:
        config = app_config.storage
        if config.type == 'filesystem':
            return _create_filesystem_provider(config, app_config.validation)
        else:
            raise StorageConfigurationError(f"Unknown storage provider type: {config.type}")

    except Exception as e:
        raise StorageConfigurationError(f"Provider creation failed: {e}") from e
```

### Request-level access:

```python
# In API endpoints
storage_service = request.app.state.storage_service
app_config = request.app.state.app_config
```

## Validation and Error Handling

### Validation rules:

1. **Pydantic field validation**: Automatic validation with descriptive errors
2. **Custom validators**: Additional business logic validation
3. **Type safety**: Strong typing prevents configuration errors
4. **Range validation**: Numeric constraints (ge, le, etc.)

### Error handling:

```python
class ConfigurationError(Exception):
    pass
```

**Error sources:**
- Missing configuration files
- Invalid YAML syntax
- Pydantic validation failures
- Environment variable type conversion errors

## Configuration Hierarchy

### Default value hierarchy:

1. **Pydantic field defaults**: Base defaults defined in model fields
2. **Factory defaults**: Auto-creation of nested configuration objects
3. **YAML file values**: Override defaults when present
4. **Environment variables**: Highest priority, override everything

### Configuration composition:

```python
AppConfig(
    storage=StorageConfig(
        type="filesystem",
        filesystem=FilesystemConfig(path="archives", timeout_seconds=10),
        cache=CacheConfig(ttl_seconds=60, max_entries=1000)
    ),
    validation=ValidationConfig(...)
)
```

## Integration with Other Components

### 1. Security module (`utils/security.py`):

```python
def validate_snapshot_id(snapshot_id: str, validation_config: ValidationConfig) -> str:
    # Uses validation_config.snapshot_id_max_length
    # Uses validation_config.snapshot_id_pattern
```

### 2. Storage providers (`storage/providers/filesystem.py`):

```python
def __init__(self, storage_path: Path, timeout_seconds: int = 10, validation_config: ValidationConfig = None):
    self.storage_path = Path(storage_path)
    self.timeout_seconds = timeout_seconds
    self.validation_config = validation_config or ValidationConfig()
```

### 3. Storage service:

```python
def create_storage_service(app_config: AppConfig, provider: Optional[StorageProviderInterface] = None) -> StorageService:
    config = app_config.storage
    return StorageService(provider, config.cache.ttl_seconds)
```

## Configuration File

### Default YAML configuration (`config/storage.yaml`):

```yaml
storage:
  type: "filesystem"
  filesystem:
    path: "archives"
    timeout_seconds: 100
  cache:
    ttl_seconds: 1000
    max_entries: 1000

validation:
  snapshot_id_pattern: '^req_[a-zA-Z0-9\-_]+_\d{8}_\d{6}$'
  snapshot_id_max_length: 100
  snapshot_directory_prefix: 'req_'
  timestamp_formats:
    - '%Y%m%d_%H%M%S'
    - '%Y-%m-%d_%H-%M-%S'
  filename_max_length: 255
  allowed_artifact_types:
    - archive.wacz
    - metadata.json
    - screenshot.png
    - singlefile.html
    - warc.file
    - document.html
  content_type_mappings:
    archive.wacz: application/zip
    metadata.json: application/json
    screenshot.png: image/png
    singlefile.html: text/html
    warc.file: application/warc
    document.html: text/html
```

## Summary

The configuration system provides a type-safe foundation with:

- Pydantic models for validation and type safety
- Environment variable overrides for flexible deployment
- YAML file support for complex configuration
- Seamless integration throughout the application
- Centralized configuration management
- Error handling and validation

The system enables flexible deployment across environments while maintaining strict type safety and validation.