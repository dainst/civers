# Archive Generator

A modular, event-driven web archiving component of the **Citation of Versioned Web Pages by PID (CiVers)** project. Generates multiple archive formats from web pages including WARC files, HTML snapshots, screenshots, and SingleFile HTML.

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/dainst/civers_archive_generator.git
cd civers_archive_generator

# Run the automated setup script
chmod +x scripts/application_setup.sh
./scripts/application_setup.sh
```

The script automatically installs all dependencies, sets up Kafka, and verifies the installation.

### Option 2: Manual Setup

```bash
# Prerequisites: Node.js 20+, Python 3.12+, Docker

# Install dependencies
uv sync
uv run playwright install chromium
cd lib/scoop && npm ci && cd ../..

# Start Kafka
docker compose up -d broker

# Start the application
uv run python main.py
```

### Test It Works

```bash
# Send test archive requests (in a new terminal)
PYTHONPATH=. uv run python scripts/send_test_requests.py https://example.com

# OPTIONAL: Send requests DIRECTLY (bypasses Kafka)
PYTHONPATH=. uv run python scripts/send_test_requests.py --direct https://example.com

# Check generated archives
ls -la archives/
```

### Output Structure

```text
archives/
└── domain_com/
    └── page_path/
        └── req_123_20250822_123456/
            ├── archive.wacz           # WACZ archive (via Scoop)
            ├── singlefile.html        # Self-contained HTML
            ├── summary.json           # Scoop processing summary
            └── metadata.json          # Archive metadata
```

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Storage Layer](#storage-layer)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Overview

The Archive Generator serves as the **content capture and preservation component** within the CiVers ecosystem for creating persistent identifiers (PIDs) for versioned web pages.

**Key Benefits:**

- 🚀 **Event-driven architecture** - Scalable Kafka-based message processing
- 📦 **Multiple formats** - WARC, HTML, screenshots, SingleFile archives
- 💾 **Multi-backend storage** - Local files and CIVERS REST API
- 🎯 **Domain-specific strategies** - Configurable archiving per domain
- 🧪 **Comprehensive testing** - Unit, integration, and E2E test coverage

## Features

### Archive Format Generation

- **📦 WACZ Archives** - Web Archive Collection Zipped format via Scoop CLI
- **🌐 HTML Snapshots** - Complete DOM capture at time of archiving  
- **📸 Screenshots** - Full-page visual snapshots as PNG images
- **🔗 SingleFile HTML** - Self-contained HTML with embedded resources
- **📋 Metadata** - Archive processing information and provenance data

### Storage Backends

- **💾 Local File Storage** - Save archives to local filesystem
- **🌐 CIVERS REST API** - Upload archives to CIVERS storage service
- **🔄 Multi-backend** - Store to multiple backends simultaneously

## Architecture

```text
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   CiVers        │    │  Archive     │    │   Storage       │
│   Request       │───▶│  Generator   │───▶│   Layer         │
│   Queue         │    │  Component   │    │   (Multi-       │
│   (Kafka)       │    │              │    │    Backend)     │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │                    │
                              │                    ├─▶ Local Files
                              ▼                    └─▶ CIVERS API
                       ┌──────────────┐
                       │  Status &    │
                       │  Events      │
                       └──────────────┘
```

### Component Structure

```text
archive_generator/
├── 🤖 archive_generators/    # Modular strategy implementations
│   ├── scoop/              # Scoop-specific capture logic
│   └── singlefile/         # SingleFile capture logic
├── ⚙️ configs/               # Configuration and data models
├── 🔄 archive_services/      # Business logic orchestration
├── 🚚 transport_services/    # Event-driven messaging (Kafka)
├── 💾 storage_layer/         # Multi-backend storage abstraction
└── 🧪 tests/                 # Comprehensive test suite
```

## Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 20.x** (required for Scoop - NOT compatible with v24+)
- **Docker & Docker Compose**
- **uv** - Python package manager

## Configuration

The application uses a **hierarchical, environment-aware configuration system** that automatically detects the runtime environment and loads appropriate settings. No manual configuration is required for most use cases.

### Configuration Architecture

```text
config/
├── loaders.py                # Configuration loading logic
├── models.py                 # Pydantic data models for validation
└── data/
    ├── defaults/            # Base configurations (shared across all environments)
    │   ├── app.yaml         # Application settings
    │   ├── kafka.yaml       # Kafka transport configuration
    │   └── domains.yaml     # Domain-specific archiving rules
    └── environments/        # Environment-specific overrides
        ├── development.yaml # Local development (default)
        ├── testing.yaml     # Unit/integration tests
        ├── docker.yaml      # Docker containers
        └── production.yaml  # Production deployment
```

### Environment Detection

The system automatically detects the environment using this priority:

1. **`CONFIG_ENVIRONMENT` variable** - Explicit environment override
2. **Docker detection** - Presence of `/.dockerenv` or `DOCKER_ENV`
3. **Test detection** - Running under pytest or `TESTING` env var
4. **Default** - Falls back to `development`

### Starting the Application in Different Environments

#### 🛠️ Development Environment (Default)

```bash
# Start with automatic detection (uses development.yaml)
uv run python main.py

# Or explicitly set the environment
CONFIG_ENVIRONMENT=development uv run python main.py
```

**Development settings:**

- Kafka: `localhost:29092` (external broker port)
- Storage: Local files + CIVERS REST API (`http://127.0.0.1:8000`)
- Archive directory: `archives/`

#### 🧪 Testing Environment

```bash
# Running tests automatically uses testing environment
uv run pytest tests/

# Or explicitly for manual testing
CONFIG_ENVIRONMENT=testing uv run python main.py
```

**Testing settings:**

- Kafka: `localhost:29093` (dedicated test port)
- Storage: Local files only (no external dependencies)
- Archive directory: `tests/archives_artifacts/`

#### 🐳 Docker Environment

When running inside a Docker container, the application uses the same hierarchical YAML configuration as local development, but with environment-specific overrides enabled via `docker.yaml`.

1. **Auto-detection**: The system detects Docker by checking for the `/.dockerenv` file.
2. **Environment Overrides**: The `CONFIG_ENVIRONMENT=docker` setting (usually set in the Dockerfile or compose file) triggers the loading of `configs/data/environments/docker.yaml`.
3. **Variable Substitution**: Sensitive or dynamic settings (like Kafka brokers) are injected into the YAML files using `${VAR_NAME}` syntax from environment variables defined in `docker-compose.yml`.

**Docker Compose Files:**

| File | Purpose |
| :--- | :--- |
| `docker-compose.yml` | Base service definitions with default values |
| `docker-compose.override.yml` | Development-specific overrides (auto-loaded) |

**Starting with Docker:**

```bash
# Start Kafka broker only (for local development)
docker compose up -d broker

# Start the full stack (Kafka + Archive Generator)
docker compose --profile app up -d

# View logs
docker compose logs -f archive-generator
```

**Docker settings:**

- Kafka: Uses Docker service hostnames for inter-container communication.
- Storage: Local + CIVERS API (`http://civers-api:8000`).
- Environment is typically set via `CONFIG_ENVIRONMENT=docker`.

#### 🚀 Production Environment

```bash
# Set for production deployment
CONFIG_ENVIRONMENT=production uv run python main.py
```

### Environment Variable Configuration

The application supports dynamic environment variable substitution within its YAML configuration files. This allows you to keep secrets or environment-specific hosts out of the repository.

**Example Syntax (`configs/data/defaults/app.yaml`):**

```yaml
app:
  archive_directory: ${ARCHIVE_DIRECTORY:-archives}
```

**Common Environment Variables:**

```bash
# Core settings
CONFIG_ENVIRONMENT=docker                    # development, testing, docker, or production
ARCHIVE_DIRECTORY=/archives

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_REQUESTS=archive.requests
KAFKA_TOPIC_STATUS=archive.status

# Storage backends
STORAGE_ENABLED="local_file,civers_rest_api"
STORAGE_API_UPLOAD_URL=http://civers-api:8000/api/upload
```

### Configuration Structure

```yaml
app:
  name: archive_generator
  version: 1.0.0
  archive_directory: archives
  
  # Scoop CLI configuration
  scoop_cli_command: "node lib/scoop/bin/cli.js"
  scoop_timeout_sec: 300
  
  # SingleFile configuration
  singlefile_binary_path: "archive_generators/single-file-x86_64-linux"
  singlefile_timeout_sec: 60
  
  # Transport configuration
  transport:
    enabled: ["kafka"]
    kafka:
      bootstrap_servers: localhost:29092
      topics:
        archive_requests: "archive.requests"
        archive_status: "archive.status"
  
  # Storage configuration
  storage:
    enabled:
      - local_file
      - civers_rest_api  # Optional: requires CIVERS API
    backends:
      local_file:
        base_path: "archives"
        create_subdirectories: true
      civers_rest_api:
        upload_url: "http://localhost:8000/api/upload"
        timeout_seconds: 30

# Domain-specific archive strategies
domains:
  - name: arachne.dainst.org
    webpage_types: dynamic
    generators:
      - name: scoop
        artifacts: [warc, screenshot, dom-snapshot]
      - name: singlefile
        artifacts: [singlefile]

  - name: example.com
    webpage_types: dynamic
    generators:
      - name: scoop
        artifacts: [warc]
```

### Debugging Configuration

```python
from config import ConfigLoaderFactory

# Check which loader and environment is being used
loader = ConfigLoaderFactory.create()
print(f"Loader type: {loader.__class__.__name__}")
print(f"Detected environment: {loader.environment}")

config = loader.load()
print(f"Storage backends: {config.app.storage.get_enabled_backends()}")
```

## Storage Layer

The Archive Generator supports multiple storage backends for storing archive metadata and artifacts.

### Supported Backends

| Backend | Description | Use Case |
| :--- | :--- | :--- |
| `local_file` | Local filesystem storage | Development, standalone deployment |
| `civers_rest_api` | CIVERS storage API | Production, centralized storage |

### Supported Artifact Types

The following artifact files can be stored:

| File | Description |
| :--- | :--- |
| `archive.wacz` | WACZ archive (via Scoop CLI) |
| `singlefile.html` | Self-contained HTML with embedded resources |
| `document.html` | DOM snapshot HTML |
| `screenshot.png` | Full-page screenshot |
| `metadata.json` | Archive processing metadata |

### Multi-Backend Configuration

Enable multiple backends to store artifacts to multiple locations simultaneously:

```yaml
app:
  storage:
    enabled:
      - local_file
      - civers_rest_api
    backends:
      local_file:
        base_path: "archives/metadata"
      civers_rest_api:
        upload_url: "http://localhost:8000/api/upload"
        timeout_seconds: 30
        auth:
          enabled: false  # Set to true and add token if required
```

### Testing Storage

Use the demo script to verify storage is working.

> [!IMPORTANT]
> Testing the `civers_rest_api` backend requires a running instance of the **CIVERS Web Interface REST API**. If the API is not reachable, these specific tests will fail.

```bash
# Test local storage only
uv run python scripts/demo_storage.py

# Test metadata upload to CIVERS API (Requires API)
uv run python scripts/demo_storage.py --with-api

# Test ALL artifact types (Requires API)
uv run python scripts/demo_storage.py --with-api --artifacts
```

## Testing

The project uses `pytest` for testing. Test dependencies can be installed via the `dev` extra:

```bash
uv sync --extra dev
```

### 1. Unit Tests (Fast)

Unit tests are isolated and have no external dependencies. They take ~5 seconds to run.

```bash
# Run all unit tests with coverage
uv run pytest tests/unit/ -v
```

> [!TIP]
> Coverage reports are automatically generated in the console and as HTML in the `cov_html/` directory.

### Test Configuration

Test settings are managed in [pytest.ini](pytest.ini). You can enable verbose logging during tests by adding the `--log-cli-level=INFO` flag.

## Troubleshooting

### Common Issues

#### Node.js Version Incompatibility

```bash
# Scoop requires Node.js v20.x
nvm install 20 && nvm use 20
```

#### Kafka Connection Failed

```bash
docker compose down && docker compose up -d
docker compose logs broker
```

#### Scoop Dependencies Missing

```bash
cd lib/scoop && npm ci && npx playwright install chromium && cd ../..
```

#### Storage API Not Reachable

```bash
# Check if CIVERS API is running
curl http://localhost:8000/health
```

### Logs and Debugging

```bash
# View application logs
tail -f archive_generator.log

# View Kafka topics
docker exec civers_archive_generator-kafka-broker-1 \
  kafka-topics.sh --bootstrap-server localhost:9092 --list
```

### Getting Help

- **Development**: See `DEVELOPMENT.md`

---

## License & Credits

### License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

### Third-Party Tools

CIVERS integrates the following open-source tools:

| Tool | License | Purpose |
| :--- | :--- | :--- |
| Scoop | MIT | Web archiving (Harvard Library Innovation Lab) |
| SingleFile | AGPL-3.0 | Self-contained HTML snapshots |
