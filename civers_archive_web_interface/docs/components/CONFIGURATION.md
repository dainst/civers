# Configuration Architecture

This directory contains the complete configuration management system for the CIVERS Archive Web Interface. The architecture provides environment-aware, hierarchical configuration loading with validation and type safety.

## 📁 Directory Structure

```text
configs/
├── __init__.py              # Package exports and public API
├── models.py                # Pydantic data models for validation
├── loaders.py               # Configuration loading logic
└── data/                    # Configuration data files
    ├── defaults/            # Base configurations (shared across environments)
    │   ├── app.yaml         # Application metadata, logging, API, database
    │   ├── server.yaml      # Server host, port, debug, CORS origins
    │   ├── storage.yaml     # Storage provider configuration
    │   ├── validation.yaml  # Input validation rules & artifact types
    │   ├── kafka.yaml       # Kafka transport configuration
    │   └── domains.yaml     # Domain-specific archiving rules
    └── environments/        # Environment-specific overrides
        └── development.yaml # Development environment overrides
```

## 🏗️ Architecture Overview

The configuration system follows a **hierarchical loading strategy** with environment-based overrides:

1. **Base Configuration**: Load all YAML files from `data/defaults/` (sorted alphabetically)
2. **Environment Detection**: Automatically detect or specify environment
3. **Environment Overrides**: Deep-merge environment-specific settings from `data/environments/`
4. **Environment Variable Expansion**: Resolve `${VAR}` and `${VAR:-default}` syntax in values
5. **Validation**: Validate the merged dictionary against Pydantic models via `AppConfig(**config)`

### Key Design Principles

- **Environment Awareness**: Automatic environment detection with manual override capability
- **Hierarchical Configuration**: Base + Environment pattern for maintainable configs
- **Type Safety**: Pydantic models ensure configuration validation at startup
- **Separation of Concerns**: Clear separation between data (YAML) and code (Python)
- **Cross-Component Consistency**: Configuration models are designed to be consistent with other CIVERS components (`civers_orchestrator`, `civers_archive_generator`, `civers_metadata_extractor`)

## 📊 Configuration Files Reference

### `app.yaml` — Application & Server Settings

Contains the core application configuration, logging, API behavior, database settings, and directory paths.

```yaml
app:
  name: "Civers Archive Web Interface"
  version: "1.0.0"
  description: "Civers Archive Web Interface for browsing and replaying archived versions of websites"
  service_name: "civers-archive-web-interface"
  environment: "${CONFIG_ENVIRONMENT:-development}"
  logging:
    level: INFO
    correlation_id_log_level: INFO
    file: null
    json_enabled: true
    kafka_log_level: WARNING
    access_log_level: INFO

api:
  pagination:
    default_page_size: 50
    max_page_size: 100
    default_page: 1
    default_offset: 0
  kafka:
    default_priority: 1
  callback_base_url: "http://localhost:8000"
  trusted_proxy_hosts:
    - "127.0.0.1"
  max_upload_size_mb: 100

database:
  connection_timeout_seconds: 10.0

directories:
  templates: "templates"
  static: "static"
  archives: "archives"
```

#### Root Sections in `app.yaml`

| Section | Model | Description |
|---------|-------|-------------|
| `app` | `AppInfoConfig` | Application metadata, environment, logging |
| `app.logging` | `LoggingConfig` | Log levels, JSON format, file output |
| `api` | `ApiConfig` | Pagination, upload limits, proxy settings |
| `database` | `DatabaseConfig` | Database connection timeouts |
| `directories` | `DirectoriesConfig` | Template, static, and archive directory paths |

---

### `server.yaml` — Server Settings

Configures the HTTP server host, port, debug mode, and CORS origins. Used by uvicorn and CORS middleware in `app/main.py`.

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  cors_origins:
    - "http://localhost:8000"
    - "http://localhost:8080"
```

| Section | Model | Description |
|---------|-------|-------------|
| `server` | `ServerConfig` | Server host, port, debug mode, CORS origins |

---

### `storage.yaml` — Storage Provider Configuration

Configures the storage backend (filesystem or SQLite) and caching behavior.

```yaml
storage:
  type: "sqlite"

  filesystem:
    path: "archives"
    timeout_seconds: 0

  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true
    connection_timeout: 10

  cache:
    ttl_seconds: 10000000
    max_entries: 1000
```

| Section | Model | Description |
|---------|-------|-------------|
| `storage` | `StorageConfig` | Provider type selection (`"filesystem"` or `"sqlite"`) |
| `storage.filesystem` | `FilesystemConfig` | Path and timeout for filesystem provider |
| `storage.sqlite` | `SQLiteConfig` | DB path, auto-rebuild, connection timeout |
| `storage.cache` | `CacheConfig` | TTL and max entries for in-memory cache |

---

### `validation.yaml` — Input Validation Rules

Defines validation patterns, allowed artifact types, and content-type mappings.

```yaml
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
    - dom-snapshot.html
    - archive_generator_metadata.json
  content_type_mappings:
    archive.wacz: application/zip
    metadata.json: application/json
    screenshot.png: image/png
    singlefile.html: text/html
    warc.file: application/warc
    document.html: text/html
    dom-snapshot.html: text/html
    archive_generator_metadata.json: application/json
```

| Section | Model | Description |
|---------|-------|-------------|
| `validation` | `ValidationConfig` | Snapshot ID patterns, allowed artifact types, content-type mappings |

---

### `kafka.yaml` — Kafka Transport Configuration

Configures the Kafka producer for publishing archive request events.

```yaml
kafka:
  bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
  producer:
    acks: "all"
    retries: 3
    batch_size: 16384
    linger_ms: 10
    request_timeout_ms: 30000
    api_version_timeout_ms: 30000
    publish_timeout_seconds: 10.0
    shutdown_timeout_seconds: 5
  topics:
    orchestrator_requests: "orchestrator.requests"
    orchestrator_status: "orchestrator.status"
  health_check_enabled: true
  monitoring_enabled: true
  connection_retry_attempts: 5
  connection_retry_delay_ms: 2000
```

| Section | Model | Description |
|---------|-------|-------------|
| `kafka` | `KafkaConfig` | Bootstrap servers, topics, health/monitoring settings |
| `kafka.producer` | `KafkaProducerConfig` | Acks, retries, batch size, timeouts |

> [!NOTE]
> The `bootstrap_servers` field uses environment variable expansion: `${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}`. This allows the same YAML to work across environments by setting the env var in Docker/production.

> [!IMPORTANT]
> At runtime, the `kafka` section from this YAML file is loaded into `AppConfig.transport.kafka` (via `TransportConfig`). Kafka enablement is controlled by `TransportConfig.enabled` (a list, default: `["kafka"]`), **not** by a field in the YAML.

---

### `domains.yaml` — Domain Configuration

Defines which domains are available for archiving in the web interface form.

```yaml
domains:
  - name: arachne.dainst.org
    enabled: true
    description: "iDAI.objects/Arachne - Archaeological object database"

  - name: arachne.test.dainst.org
    enabled: true
    description: "Arachne test environment"

  - name: field.dainst.org
    enabled: true
    description: "iDAI.field - Field documentation"

  - name: publications.dainst.org
    enabled: true
    description: "DAINST Publications"

  - name: "*.dainst.org"
    enabled: true
    description: "Default pattern for DAI domains"

  - name: default
    enabled: true
    description: "Default fallback for unknown domains"

  - name: httpbin.org
    enabled: true
    description: "HTTP testing service for integration tests"
```

| Section | Model | Description |
|---------|-------|-------------|
| `domains` | `List[DomainConfig]` | Domain names/patterns with enabled flag and description |

---

## 🌍 Environment Overrides

### Available Environments

| Environment | Source | Detection |
|-------------|--------|-----------|
| `development` | `development.yaml` | Default fallback |
| `testing` | — | Auto-detected via `PYTEST_CURRENT_TEST` env var |
| `docker` | — | Auto-detected via `/.dockerenv` file |

#### Environment Detection Priority

1. `CONFIG_ENVIRONMENT` environment variable (explicit)
2. `/.dockerenv` file exists → `docker`
3. `PYTEST_CURRENT_TEST` env var set → `testing`
4. Default → `development`

### `development.yaml`

```yaml
domains:
  - name: localhost:8080
    enabled: true
    description: "local Arachne instance"
app:
  logging:
    level: INFO
    access_log_level: INFO
```

Environment files can override **any** section from the defaults. Values are deep-merged, so only the specific fields that need to change must be specified.

## 📋 Configuration Data Models

All configuration is validated at startup using Pydantic models defined in `configs/models.py`.

### `AppConfig` — Root Model

The top-level model that receives the merged YAML dictionary:

```python
class AppConfig(BaseModel):
    app: AppInfoConfig           # From app.yaml → app:
    api: ApiConfig               # From app.yaml → api:
    database: DatabaseConfig     # From app.yaml → database:
    directories: DirectoriesConfig # From app.yaml → directories:
    server: ServerConfig         # From server.yaml → server:
    storage: StorageConfig       # From storage.yaml → storage:
    validation: ValidationConfig # From validation.yaml → validation:
    transport: TransportConfig   # From kafka.yaml → kafka: (wrapped)
    domains: List[DomainConfig]  # From domains.yaml → domains:
```

> [!NOTE]
> `AppConfig` provides a `config.kafka` property shortcut that returns `config.transport.kafka`, so you can access Kafka settings either way.

### Key Model Details

#### `LoggingConfig` (nested under `app.logging`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | `str` | `"INFO"` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `correlation_id_log_level` | `str` | `"INFO"` | Log level for correlation ID middleware |
| `file` | `str?` | `null` | Path to log file |
| `json_enabled` | `bool` | `true` | Enable JSON logging format |
| `kafka_log_level` | `str` | `"WARNING"` | Log level for Kafka library |
| `access_log_level` | `str` | `"INFO"` | Log level for uvicorn.access |

#### `ApiConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pagination.default_page_size` | `int` | `50` | Default page size (1–1000) |
| `pagination.max_page_size` | `int` | `100` | Maximum page size (1–1000) |
| `callback_base_url` | `str?` | `"http://localhost:8000"` | Base URL for orchestrator callbacks |
| `trusted_proxy_hosts` | `List[str]` | `["127.0.0.1"]` | Trusted proxy hosts |
| `max_upload_size_mb` | `int` | `100` | Maximum file upload size in MB |

#### `ServerConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | `str` | `"0.0.0.0"` | Server bind host |
| `port` | `int` | `8000` | Server port |
| `debug` | `bool` | `false` | Enable debug mode (auto-reload templates) |
| `cors_origins` | `List[str]` | `["http://localhost:8000", "http://localhost:8080"]` | Allowed CORS origins |

#### `StorageConfig`

> [!NOTE]
> The "Default" column shows the **effective runtime default** from the YAML files, not the Pydantic model fallback.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `Literal` | `"sqlite"` | Provider type: `"filesystem"` or `"sqlite"` |
| `filesystem.path` | `str` | `"archives"` | Path to archives directory |
| `filesystem.timeout_seconds` | `int` | `0` | Filesystem operation timeout |
| `sqlite.db_path` | `str` | `"data/archives.db"` | Path to SQLite database file |
| `sqlite.auto_rebuild` | `bool` | `true` | Auto-rebuild index if DB empty |
| `sqlite.connection_timeout` | `int` | `10` | Connection timeout in seconds |
| `cache.ttl_seconds` | `int` | `10000000` | Cache TTL in seconds (`-1` for no expiry) |
| `cache.max_entries` | `int` | `1000` | Maximum cache entries |

#### `ValidationConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `snapshot_id_pattern` | `str` | `'^req_...'` | Regex for snapshot ID validation |
| `snapshot_id_max_length` | `int` | `100` | Max snapshot ID length |
| `snapshot_directory_prefix` | `str` | `"req_"` | Prefix for snapshot directories |
| `timestamp_formats` | `List[str]` | `[...]` | Supported timestamp formats |
| `filename_max_length` | `int` | `255` | Maximum filename length |
| `allowed_artifact_types` | `Set[str]` | 8 types | Allowed artifact file types |
| `content_type_mappings` | `Dict[str,str]` | 8 mappings | MIME type mappings |

#### `TransportConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `List[str]` | `["kafka"]` | Enabled transport mechanisms |
| `kafka` | `KafkaConfig` | — | Kafka configuration (see below) |

#### `KafkaConfig` (nested under `transport.kafka`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bootstrap_servers` | `str` | `"localhost:29092"` | Kafka broker connection (supports `${}` expansion) |
| `topics` | `Dict[str,str]` | 2 topics | Topic name mappings |
| `producer.*` | `KafkaProducerConfig` | — | Producer acks, retries, timeouts |
| `health_check_enabled` | `bool` | `true` | Enable Kafka health check |
| `monitoring_enabled` | `bool` | `true` | Enable monitoring |
| `connection_retry_attempts` | `int` | `5` | Retry attempts |
| `connection_retry_delay_ms` | `int` | `2000` | Retry delay in ms |

#### `DomainConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | **required** | Domain name or pattern (e.g., `"*.dainst.org"`) |
| `enabled` | `bool` | `true` | Whether domain is enabled |
| `description` | `str` | `""` | Human-readable description |

## 🔧 Configuration Loading (`loaders.py`)

### `YamlFileConfigLoader`

The primary configuration loader that manages hierarchical loading and merging.

#### Environment Variable Expansion

YAML values can reference environment variables:

- `${VAR_NAME}`: Simple substitution
- `${VAR_NAME:-default}`: Substitution with default fallback
- `"prefix_${VAR}_suffix"`: Partial substitution
- `"${VAR1}:${VAR2}"`: Multiple variables

#### Usage

```python
from configs.loaders import YamlFileConfigLoader

loader = YamlFileConfigLoader()
config = loader.load()

# Access values
log_level = config.app.logging.level
storage_type = config.storage.type
cors_origins = config.server.cors_origins
kafka_servers = config.transport.kafka.bootstrap_servers
# or via shortcut property:
kafka_servers = config.kafka.bootstrap_servers
```

## 🚀 Extending the Configuration

### Adding a New Environment

1. Create `data/environments/<name>.yaml` with overrides
2. Set `CONFIG_ENVIRONMENT=<name>` when running

### Adding New Configuration Sections

1. Add Pydantic model in `models.py`
2. Add new model field to `AppConfig`
3. Add default values in `data/defaults/`
4. Add environment overrides as needed

## 🔒 Security Considerations

- Never commit sensitive data to configuration files
- Use environment variable expansion for secrets: `${SECRET_KEY}`
- Ensure test environments cannot access production data
- Use different Kafka clusters/topics per environment

---

**Note**: This configuration system is consistent with the pattern used across all CIVERS components (`civers_orchestrator`, `civers_archive_generator`, `civers_metadata_extractor`).
