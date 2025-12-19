# CIVERS Shared Configuration

This directory contains centralized configuration files that serve as a single source of truth for all CIVERS components.

## Directory Structure

```
configs/
├── defaults/               # Base configuration files
│   ├── domains.yaml        # Merged domain definitions (workflows + artifacts)
│   ├── kafka.yaml          # Unified Kafka topic definitions
│   ├── storage.yaml        # Shared storage backend configuration
│   └── workflows.yaml      # Workflow definitions (Orchestrator-specific)
└── environments/           # Environment-specific overrides
    ├── development.yaml    # Local development settings
    ├── docker.yaml         # Docker container settings
    ├── testing.yaml        # Pytest/automated testing settings
    └── production.yaml     # Production deployment settings
```

## Usage

### Setting CONFIG_DIR

Components should be started with `CONFIG_DIR` pointing to this directory:

```bash
# From component directory
CONFIG_DIR=../configs uv run python main.py

# Or as environment variable
export CONFIG_DIR=/path/to/civers_project/configs
```

### Environment Selection

The environment is detected automatically:
1. `CONFIG_ENVIRONMENT` env var (highest priority)
2. Docker detection (`/.dockerenv` file)
3. Pytest detection (`PYTEST_CURRENT_TEST` env var)
4. Default to `development`

Or explicitly set:
```bash
CONFIG_ENVIRONMENT=docker CONFIG_DIR=../configs uv run python main.py
```

## Domain Configuration

The `domains.yaml` file contains merged attributes for all components:

```yaml
domains:
  - name: arachne.dainst.org
    workflow: archaeology_workflow     # Used by Orchestrator
    artifacts: [warc, html, screenshots] # Used by Generator
    webpage_types: dynamic              # Used by Generator
    enabled: true
    description: "Archaeological database"
```

Each component extracts only the attributes it needs:
- **Orchestrator**: Uses `workflow` to route requests
- **Generator**: Uses `artifacts` and `webpage_types` for archiving

## Kafka Topics

All topic names are defined in `kafka.yaml` to ensure consistency:

| Component | Request Topic | Completed Topic | Failed Topic |
|-----------|---------------|-----------------|--------------|
| Orchestrator | orchestrator.requests | orchestrator.completed | orchestrator.failed |
| Archive Generator | archive.requests | archive.completed | archive.failed |
| Metadata Extractor | metadata.requests | metadata.completed | metadata.failed |

## Storage Backends

Configured in `storage.yaml`:
- `local_file`: Local filesystem storage
- `civers_rest_api`: Upload to CIVERS Web Interface API

## Environment Variables

All configuration values support environment variable expansion:

```yaml
bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
```

Common variables:
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker address
- `KAFKA_CONSUMER_GROUP_ID` - Consumer group name
- `ARCHIVE_DIRECTORY` - Local archive storage path
- `CIVERS_API_URL` - Web Interface API endpoint
- `CONFIG_ENVIRONMENT` - Force specific environment
- `CONFIG_DIR` - Path to this configs directory
