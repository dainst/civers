# Configuration Architecture

This directory contains the complete configuration management system for the CIVERS Archive Generator. The architecture provides environment-aware, hierarchical configuration loading with validation and type safety.

## 📁 Directory Structure

```text
config/
├── README.md                 # This documentation
├── __init__.py              # Package exports and public API
├── models.py                # Pydantic data models for validation
├── loaders.py               # Configuration loading logic
├── logging_config.py        # Logging setup and configuration
└── data/                    # Configuration data files
    ├── defaults/            # Base configurations (shared across environments)
    │   ├── app.yaml         # Application settings
    │   ├── kafka.yaml       # Kafka transport configuration
    │   └── domains.yaml     # Domain-specific archiving rules
    └── environments/        # Environment-specific overrides
        ├── testing.yaml     # Test environment settings
        ├── development.yaml # Development environment settings
        ├── docker.yaml      # Docker container settings
        └── production.yaml  # Production environment settings
```

## 🏗️ Architecture Overview

The configuration system follows a **hierarchical loading strategy** with environment-based overrides:

1. **Base Configuration**: Load defaults from `data/defaults/`
2. **Environment Detection**: Automatically detect or specify environment
3. **Environment Overrides**: Apply environment-specific settings from `data/environments/`
4. **Deep Merging**: Intelligently merge configurations with environment precedence
5. **Validation**: Validate final configuration using Pydantic models

### Key Design Principles

- **Environment Awareness**: Automatic environment detection with manual override capability
- **Hierarchical Configuration**: Base + Environment pattern for maintainable configs
- **Type Safety**: Pydantic models ensure configuration validation
- **Separation of Concerns**: Clear separation between data (YAML) and code (Python)
- **Multi-Backend Storage**: Support for multiple storage backends simultaneously

## 📋 Configuration Data Model

### Core Models (`models.py`)

#### `ConfigDataModel`

The root configuration object containing:

- `app`: Application-level configuration (`AppConfig`) - **required**
- `domains`: List of domain-specific configurations (`DomainConfig`)

#### `AppConfig`

Application settings including:

- `name`: Application name
- `version`: Application version
- `archive_directory`: Where archives are stored
- `transport`: Transport layer configuration (`TransportConfig`) - **required**
- `storage`: Storage backend configuration (`StorageConfig`) - **required**

#### `TransportConfig`

Transport layer configuration supporting multiple transports:

- `enabled`: List of enabled transports (e.g., `["kafka"]`) - **required, non-empty**
- `kafka`: Kafka-specific configuration (`KafkaConfig`)
- `transports`: Dict for additional transport configurations

#### `KafkaConfig`

Kafka transport settings:

- `bootstrap_servers`: Kafka broker connection string - **required**
- `topics`: Topic names for different event types - **required**
- `consumer_group`: Consumer group ID - **required**
- `health_check_enabled`: Enable health monitoring (default: `true`)
- `monitoring_enabled`: Enable metrics collection (default: `true`)

#### `DomainConfig`

Domain-specific archiving rules:

- `name`: Domain name (e.g., "example.com") - **required**
- `generators`: List of specialized generators (`GeneratorConfig`) - **required, non-empty**
- `webpage_types`: Type of web content ("dynamic" or "static") - **required**
- `enabled`: Enable/disable this domain (default: `true`)
- `description`: Optional documentation for this domain

#### `GeneratorConfig`

Individual generator settings within a domain:

- `name`: Generator type (e.g., `scoop`, `singlefile`) - **required**
- `artifacts`: List of specific artifacts to produce (e.g., `["warc", "screenshot"]`) - **required**

#### `StorageConfig`

Multi-backend storage configuration:

- `enabled`: List of enabled storage backends - **required, non-empty**
- `backends`: Dict of backend-specific configurations

```python
# Example StorageConfig
storage_config = StorageConfig(
    enabled=["local_file", "civers_rest_api"],
    backends={
        "local_file": {"base_path": "archives"},
        "civers_rest_api": {"upload_url": "http://localhost:8000/api/upload"}
    }
)
```

## 🔧 Configuration Loading (`loaders.py`)

### `YamlFileConfigLoader`

The primary configuration loader that manages the hierarchical loading and merging process.

#### Environment Detection

The system automatically detects the environment using this priority:

1. **`CONFIG_ENVIRONMENT` environment variable**: Explicitly set to `development`, `testing`, `docker`, or `production`.
2. **Docker Detection**: Presence of the `/.dockerenv` file.
3. **Pytest Detection**: Automatically detected when running under `pytest`.
4. **Default**: Falls back to `development`.

#### Environment Variable Expansion

The loader supports dynamic environment variable substitution within YAML files using the following syntax:

- `${VAR_NAME}`: Simple variable substitution.
- `${VAR_NAME:-default}`: Substitution with a default value if the variable is not set.

Example in `app.yaml`:

```yaml
app:
  archive_directory: ${ARCHIVE_DIRECTORY:-archives}
```

#### Usage Example

```python
from configs.loaders import YamlFileConfigLoader

# Initialize and load
loader = YamlFileConfigLoader()
config = loader.load()

print(f"Detected Environment: {loader.environment}")
```

## 📊 Environment Configurations

### Available Environments

#### `testing` Environment

- **Purpose**: Unit and integration tests
- **Kafka**: `localhost:29093` (test broker)
- **Archive Directory**: `tests/archives_artifacts`
- **Storage**: Local file only

#### `development` Environment (Default)

- **Purpose**: Local development
- **Kafka**: `localhost:29092` (development broker)
- **Archive Directory**: `archives`
- **Storage**: Local file + CIVERS REST API

#### `docker` Environment

- **Purpose**: Docker containerized deployment
- **Kafka**: `localhost:9092` (container broker)
- **Archive Directory**: `archives`
- **Storage**: Local file + CIVERS REST API

#### `production` Environment

- **Purpose**: Production deployment
- **Kafka**: `localhost:9092` (production broker)
- **Archive Directory**: `archives`
- **Storage**: Local file + CIVERS REST API

### Environment-Specific Overrides

Each environment can override any base configuration. Example `testing.yaml`:

```yaml
app:
  transport:
    kafka:
      bootstrap_servers: "localhost:29093"
  archive_directory: "tests/archives_artifacts"
  storage:
    enabled:
      - local_file
    backends:
      local_file:
        base_path: tests/archives_artifacts
```

## 🧪 Testing Architecture

### Test Coverage

The configuration system is thoroughly tested across multiple test suites:

#### Unit Tests

- **Location**: `tests/unit/configs/`
- **Coverage**:
  - Configuration loading logic
  - Environment detection
  - Data model validation
  - Error handling

#### Integration Tests

- **Location**: `tests/integration/`
- **Coverage**:
  - End-to-end configuration loading
  - Environment-specific behavior
  - Real service integration

### Mock Configuration for Tests

```python
from config.models import (
    ConfigDataModel, AppConfig, KafkaConfig, 
    TransportConfig, StorageConfig, DomainConfig
)

# Create test configuration with all required fields
test_config = ConfigDataModel(
    app=AppConfig(
        name="test-app",
        version="1.0.0",
        archive_directory="test_archives",
        singlefile_binary_path="/usr/bin/singlefile",
        transport=TransportConfig(
            enabled=["kafka"],
            kafka=KafkaConfig(
                bootstrap_servers="localhost:29093",
                topics={
                    "archive_requests": "test.archive.requests",
                    "archive_status": "test.archive.status"
                },
                consumer_group="test_group"
            )
        ),
        storage=StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "test_archives"}}
        )
    ),
    domains=[
        DomainConfig(
            name="example.com",
            artifacts=["warc", "html"],
            webpage_types="dynamic"
        )
    ]
)
```

## 🏗️ Modular Generator Configuration

 The archive generator uses a **Factory-based modular architecture** for its generation logic. This allows for mixing and matching different tools while maintaining strict control over the output.

### 🌟 Benefits of the New Configuration

 1. **Strict Artifact Control**: You can specify EXACTLY which files a generator should keep. For example, if you use `scoop` but only want the `warc`, the system will automatically purge unrequested screenshots, DOM snapshots, and logs.
 2. **Modularity**: Multiple generators can be chained together for a single domain (e.g., using `scoop` for WACZ and `singlefile` for a standalone HTML file).
 3. **Reduced Noise**: Centralized cleanup ensures that the archive directory contains only requested artifacts and essential metadata (`metadata.json`, `summary.json`), eliminating log clutter.
 4. **Flexibility**: New generators can be added by implementing the `ArchiveGeneratorStrategyInterface` without changing the core service logic.

### Example Configuration (`domains.yaml`)

 ```yaml
 domains:
   - name: example.com
     generators:
       - name: scoop
         artifacts: [warc, dom-snapshot]  # Screenshot will be purged even if Scoop takes it
       - name: singlefile
         artifacts: [singlefile]
     webpage_types: dynamic
 ```

## 🔨 Usage Patterns

### Basic Configuration Loading

```python
from config import ConfigLoaderFactory

# Load configuration with automatic environment detection
loader = ConfigLoaderFactory.create()
config = loader.load()

# Access configuration values
kafka_servers = config.app.transport.kafka.bootstrap_servers
archive_dir = config.app.archive_directory
storage_backends = config.app.storage.get_enabled_backends()
```

### Service Integration

```python
from config import ConfigLoaderFactory
from transport_services import KafkaTransportService
from archive_services import ArchiveService

# Load configuration
loader = ConfigLoaderFactory.create()
config = loader.load()

# Initialize services with configuration
archive_service = ArchiveService(config)
transport_service = KafkaTransportService(config, archive_service)
```

### Storage Configuration

```python
# Get storage config
storage_config = config.app.get_storage_config()

# Get list of enabled backends
enabled = storage_config.get_enabled_backends()
# ['local_file', 'civers_rest_api']

# Get backend-specific configuration
local_config = storage_config.get_backend_config("local_file")
# {'base_path': 'archives', 'create_subdirectories': True}
```

## 🚀 Extending the Configuration System

### Adding New Environment

1. Create new environment file: `data/environments/staging.yaml`
2. Define environment-specific overrides
3. Add tests for new environment

### Adding New Configuration Sections

1. **Update Models**: Add new Pydantic model in `models.py`
2. **Update Base Config**: Add default values in `data/defaults/`
3. **Update Environments**: Add overrides in environment files
4. **Update Tests**: Add test coverage for new configuration
5. **Update Documentation**: Document new configuration options

### Adding New Storage Backend

1. Add backend name to `enabled` list in storage config
2. Add backend configuration to `backends` dict
3. Register strategy in `StorageStrategyRegistry`
4. Implement `StorageStrategy` interface

```yaml
# Example: Adding S3 backend
storage:
  enabled:
    - local_file
    - s3
  backends:
    local_file:
      base_path: archives
    s3:
      bucket: my-archive-bucket
      region: us-east-1
```

## 🔍 Debugging Configuration Issues

### Environment Detection Problems

```python
from config import ConfigLoaderFactory

loader = ConfigLoaderFactory.create()
print(f"Loader type: {loader.__class__.__name__}")
print(f"Detected environment: {loader.environment}")
```

### Configuration Loading Problems

```python
from config import ConfigLoaderFactory
from pydantic import ValidationError

try:
    loader = ConfigLoaderFactory.create()
    config = loader.load()
    print("✅ Configuration loaded successfully")
    print(f"   Environment: {loader.environment}")
    print(f"   Storage backends: {config.app.storage.get_enabled_backends()}")
except ValidationError as e:
    print("Configuration validation errors:")
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")
except Exception as e:
    print(f"❌ Configuration loading failed: {e}")
```

## 📈 Performance Considerations

### Configuration Caching

The configuration is loaded once per application instance. For better performance in testing:

```python
# Cache configuration for multiple tests
@pytest.fixture(scope="session")
def app_config():
    loader = ConfigLoaderFactory.create()
    return loader.load()
```

### Memory Usage

Configuration objects are lightweight and designed for minimal memory footprint.

## 🔒 Security Considerations

### Sensitive Data

- Never commit sensitive data to configuration files
- Use environment variables for secrets in production
- Consider encrypted configuration for sensitive environments

### Environment Isolation

- Ensure test environments cannot access production data
- Use different Kafka clusters/topics per environment
- Implement proper access controls for configuration files


---

**Note**: This configuration system is designed to be the single source of truth for all application settings. Changes should be made carefully with full test coverage.
