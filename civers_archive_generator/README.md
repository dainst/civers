# Archive Generator

A modular, event-driven web archiving component of the **Citation of Versioned Web Pages by PID (CiVers)** project. Generates multiple archive formats from web pages including WARC files, HTML snapshots, screenshots, and SingleFile HTML.

## 🚀 Quick Start

Get the Archive Generator running in under 5 minutes!

### Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd civers_archive_generator

# Run the automated setup script
chmod +x application_setup.sh
./application_setup.sh
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
uv run python main_app.py
```

### Test It Works

```bash
# Send test archive requests (in a new terminal)
uv run python send_test_requests.py https://example.com

# Check generated archives
ls -la archives/
```

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Storage Layer](#storage-layer)
- [Usage](#usage)
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
├── 🤖 archive_generators/    # Archive strategy implementations
├── ⚙️ config/                # Configuration and data models
├── 🔄 archive_services/      # Business logic layer
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

### Automated Setup

```bash
./application_setup.sh
```

### Manual Installation

```bash
# 1. Install Node.js v20 (if needed)
nvm install 20 && nvm use 20

# 2. Install Python dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 3. Install Playwright browsers
uv run playwright install chromium

# 4. Install Scoop dependencies
cd lib/scoop && npm ci && npx playwright install chromium && cd ../..

# 5. Set permissions
chmod +x archive_generators/single-file-x86_64-linux
mkdir -p archives

# 6. Start Kafka
docker compose up -d
```

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

1. **`ARCHIVE_ENV` variable** - Explicit environment override
2. **Docker detection** - Presence of `/.dockerenv` or `DOCKER_ENV`
3. **Test detection** - Running under pytest or `TESTING` env var
4. **Default** - Falls back to `development`

### Starting the Application in Different Environments

#### 🛠️ Development Environment (Default)

```bash
# Start with automatic detection (uses development.yaml)
uv run python main_app.py

# Or explicitly set the environment
ARCHIVE_ENV=development uv run python main_app.py
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
ARCHIVE_ENV=testing uv run python main_app.py
```

**Testing settings:**

- Kafka: `localhost:29093` (dedicated test port)
- Storage: Local files only (no external dependencies)
- Archive directory: `tests/archives_artifacts/`

#### 🐳 Docker Environment

**How Docker Configuration Works:**

When running inside a Docker container, the application uses `EnvironmentConfigLoader` instead of `YamlFileConfigLoader`. This is because:

1. **Auto-detection**: The `ConfigLoaderFactory` detects Docker by checking for `/.dockerenv` file or `DOCKER_ENV` environment variable
2. **Environment Variables**: All configuration is read from environment variables set in `docker-compose.yml` or `docker-compose.override.yml`
3. **No YAML files needed**: The container doesn't need to access the `configs/data/` YAML files

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Docker Configuration Flow                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  docker-compose.yml          docker-compose.override.yml            │
│  (base settings)             (environment-specific overrides)       │
│         │                              │                            │
│         └──────────┬───────────────────┘                            │
│                    ▼                                                │
│         Environment Variables                                       │
│         (KAFKA_BOOTSTRAP_SERVERS, ARCHIVE_ENV, etc.)               │
│                    │                                                │
│                    ▼                                                │
│         ConfigLoaderFactory.create()                                │
│                    │                                                │
│                    ▼                                                │
│         Detects Docker → EnvironmentConfigLoader                    │
│                    │                                                │
│                    ▼                                                │
│         Reads env vars → ConfigDataModel                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Docker Compose Files:**

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base service definitions with default values |
| `docker-compose.override.yml` | Development-specific overrides (auto-loaded) |

**Starting with Docker:**

```bash
# Start Kafka broker only (for local development)
docker compose up -d broker

# Start the full stack (Kafka + Archive Generator)
docker compose --profile app up -d

# Start with Kafka UI for debugging
docker compose --profile app --profile ui up -d

# View logs
docker compose logs -f archive-generator
```

**Docker settings:**

- Kafka: `localhost:9092` (internal) or `localhost:29092` (external)
- Storage: Local + CIVERS API (`http://civers-api:8000`)
- Uses Docker service hostnames for inter-container communication
- Environment is set via `ARCHIVE_ENV=docker` in Dockerfile

#### 🚀 Production Environment

```bash
# Set for production deployment
ARCHIVE_ENV=production uv run python main_app.py
```

**Production settings:**

- Kafka: `localhost:9092` (production brokers)
- Storage: Local backup + CIVERS API (with SSL verification)
- Higher timeout/retry values for reliability

### Environment Variable Configuration (Docker/Containers)

When running in Docker, the `EnvironmentConfigLoader` reads all configuration from environment variables. These are set in your `docker-compose.yml` or `docker-compose.override.yml`:

**docker-compose.yml (base configuration):**

```yaml
services:
  archive-generator:
    environment:
      ARCHIVE_ENV: ${ARCHIVE_ENV:-docker}
      KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
      KAFKA_TOPIC_REQUESTS: ${KAFKA_TOPIC_REQUESTS:-archive.requests}
      KAFKA_TOPIC_STATUS: ${KAFKA_TOPIC_STATUS:-archive.status}
      KAFKA_CONSUMER_GROUP: ${KAFKA_CONSUMER_GROUP:-archive_generator_group}
      ARCHIVE_DIRECTORY: ${ARCHIVE_DIRECTORY:-archives}
```

**docker-compose.override.yml (development overrides):**

```yaml
services:
  archive-generator:
    environment:
      ARCHIVE_ENV: development
      KAFKA_BOOTSTRAP_SERVERS: localhost:29092
      # Storage configuration
      STORAGE_ENABLED: "local_file,civers_rest_api"
      STORAGE_API_UPLOAD_URL: http://civers-api:8000/api/upload
```

**All Supported Environment Variables:**

```bash
# Core settings
APP_NAME=archive_generator
ARCHIVE_DIRECTORY=/archives
ARCHIVE_ENV=docker                    # Triggers EnvironmentConfigLoader

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_REQUESTS=archive.requests
KAFKA_TOPIC_STATUS=archive.status
KAFKA_TOPIC_COMPLETED=archive.completed
KAFKA_TOPIC_FAILED=archive.failed
KAFKA_CONSUMER_GROUP=archive_generator_group

# Storage backends (comma-separated or JSON array)
STORAGE_ENABLED="local_file,civers_rest_api"

# Local file backend
STORAGE_LOCAL_BASE_PATH=/archives
STORAGE_LOCAL_CREATE_SUBDIRS=true

# CIVERS REST API backend
STORAGE_API_UPLOAD_URL=http://civers-api:8000/api/upload
STORAGE_API_TIMEOUT=30
STORAGE_API_RETRIES=3
STORAGE_API_VERIFY_SSL=true
STORAGE_API_AUTH_ENABLED=false
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
    artifacts: [warc, html, screenshots, singlefile]
    webpage_types: dynamic
  - name: example.com
    artifacts: [warc, html, singlefile]
    webpage_types: dynamic
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
|---------|-------------|----------|
| `local_file` | Local filesystem storage | Development, standalone deployment |
| `civers_rest_api` | CIVERS storage API | Production, centralized storage |

### Supported Artifact Types

The following artifact files can be stored:

| File | Description |
|------|-------------|
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

Use the demo script to verify storage is working:

```bash
# Test local storage only
uv run python demo_storage.py

# Test metadata upload to CIVERS API
uv run python demo_storage.py --with-api

# Test ALL artifact types (wacz, html, png, etc.)
uv run python demo_storage.py --with-api --artifacts
```

Example output with full artifact testing:

```text
============================================================
🧪 Archive Generator - Storage Layer Demo
============================================================

📁 Testing LOCAL FILE Storage
   ✅ Local storage test PASSED!

🌐 Testing CIVERS REST API Storage (Metadata)
   ✅ API is running!
   ✅ civers_rest_api: req_api_test_123_20251209

📦 Testing ARTIFACT UPLOAD (All File Types)
   ✓ metadata.json (413 bytes)
   ✓ singlefile.html (308 bytes)
   ✓ document.html (172 bytes)
   ✓ screenshot.png (67 bytes)
   ✓ archive.wacz (434 bytes)
   ✅ Upload successful!

🔍 Verifying artifacts...
   ✅ metadata.json: 413 bytes
   ✅ singlefile.html: 308 bytes
   ✅ document.html: 172 bytes
   ✅ screenshot.png: 67 bytes
   ✅ archive.wacz: 434 bytes

📊 FINAL RESULTS
   local_file: ✅ PASSED
   api_metadata: ✅ PASSED
   artifact_upload: ✅ PASSED
   artifact_metadata.json: ✅ PASSED
   artifact_singlefile.html: ✅ PASSED
   artifact_document.html: ✅ PASSED
   artifact_screenshot.png: ✅ PASSED
   artifact_archive.wacz: ✅ PASSED

🎉 All tests passed!

```

## Usage

### Start the Application

```bash
# Start Kafka
docker compose up -d

# Start Archive Generator
uv run python main_app.py
```

### Send Archive Requests

```bash
# Archive default test URLs
uv run python send_test_requests.py

# Archive specific URLs
uv run python send_test_requests.py https://example.com

# Archive multiple URLs
uv run python send_test_requests.py https://example.com https://httpbin.org/get

# Use different environment
uv run python send_test_requests.py --environment=testing https://example.com
```

### View Generated Archives

```bash
ls -la archives/example_com/
# archive.wacz, screenshot.png, singlefile.html, metadata.json
```

### Output Structure

```
archives/
└── domain_com/
    └── page_path/
        └── req_123_20250822_123456/
            ├── archive.wacz           # WACZ archive (via Scoop)
            ├── singlefile.html        # Self-contained HTML
            ├── summary.json           # Scoop processing summary
            └── metadata.json          # Archive metadata
```

## Testing

### Quick Unit Tests

```bash
# Run fast unit tests (~5 seconds)
uv run pytest -k "not (kafka or integration or e2e)" -v
```

### Integration Tests

```bash
# Ensure Kafka is running
docker compose up -d

# Run integration tests
uv run pytest tests/integration/ --run-integration -v
```

### Storage Layer Tests

```bash
# Unit tests
uv run pytest tests/unit/storage_layer/ -v

# Integration tests
uv run pytest tests/integration/test_storage_layer_integration.py --run-integration -v

# Demo verification
uv run python demo_storage.py --with-api
```

### Full Test Suite

```bash
uv run pytest -v --maxfail=5
```

## Troubleshooting

### Common Issues

**Node.js Version Incompatibility**

```bash
# Scoop requires Node.js v20.x
nvm install 20 && nvm use 20
```

**Kafka Connection Failed**

```bash
docker compose down && docker compose up -d
docker compose logs broker
```

**Scoop Dependencies Missing**

```bash
cd lib/scoop && npm ci && npx playwright install chromium && cd ../..
```

**Storage API Not Reachable**

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

- **Configuration**: See `config/README.md`
- **Development**: See `DEVELOPMENT.md`
- **Troubleshooting**: See `TROUBLESHOOTING.md`
- **Architecture**: See `docs/` directory

---

## License

This project is part of the CiVers initiative for citation of versioned web pages.
