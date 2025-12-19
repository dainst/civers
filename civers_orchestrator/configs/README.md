# Configuration System

This document explains the configuration architecture for the CiVers Orchestrator.

## Overview

The configuration system uses a **hierarchical YAML-based approach** with environment variable support. Configuration is loaded in layers, with later layers overriding earlier ones.

```text
┌─────────────────────────────────────────────────────────────────┐
│  1. Default YAML files (configs/data/defaults/*.yaml)          │
├─────────────────────────────────────────────────────────────────┤
│  2. Environment-specific YAML (configs/data/environments/*.yaml)│
├─────────────────────────────────────────────────────────────────┤
│  3. Environment variable substitution (${VAR:-default})         │
├─────────────────────────────────────────────────────────────────┤
│  4. Pydantic validation (configs/models.py)                     │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```text
configs/
├── README.md              # This file
├── __init__.py
├── loaders.py             # Configuration loading logic
├── models.py              # Pydantic validation models
├── logging_config.py      # Logging configuration
└── data/
    ├── defaults/          # Base configuration (always loaded)
    │   ├── app.yaml           # Application metadata
    │   ├── domains.yaml       # Domain-to-workflow mappings
    │   ├── kafka.yaml         # Kafka transport settings
    │   └── workflows.yaml     # Workflow definitions
    └── environments/      # Environment-specific overrides
        ├── development.yaml   # Local development
        ├── docker.yaml        # Docker container
        ├── production.yaml    # Production deployment
        └── testing.yaml       # Unit testing
```

---

## CONFIG_ENVIRONMENT Variable

The `CONFIG_ENVIRONMENT` variable determines which environment configuration file to load.

**The value must match the filename** in `configs/data/environments/` (without the `.yaml` extension):

| CONFIG_ENVIRONMENT | Loads File |
|--------------------|------------|
| `development` | `environments/development.yaml` |
| `docker` | `environments/docker.yaml` |
| `production` | `environments/production.yaml` |
| `testing` | `environments/testing.yaml` |

### Auto-Detection (When Not Set)

If `CONFIG_ENVIRONMENT` is not set, the environment is auto-detected:

1. **Docker detection** → If `/.dockerenv` file exists → `docker`
2. **Pytest detection** → If `PYTEST_CURRENT_TEST` env var exists → `testing`
3. **Default** → `development`

### Error on Invalid Environment

If you explicitly set `CONFIG_ENVIRONMENT` to a non-existent file, the loader raises an error:

```bash
CONFIG_ENVIRONMENT=non-existent uv run python main.py
# FileNotFoundError: Environment file '.../environments/non-existent.yaml' not found.
# Environment 'non-existent' was explicitly set via CONFIG_ENVIRONMENT but no
# corresponding configuration file exists.
# Available environments: development, docker, production, testing
```

**Note:** The variable must be set on the **same command line** or exported first:

```bash
# ✅ Correct - on same line
CONFIG_ENVIRONMENT=docker uv run python main.py

# ✅ Correct - exported first
export CONFIG_ENVIRONMENT=docker
uv run python main.py

# ❌ Wrong - separate commands (variable not passed)
CONFIG_ENVIRONMENT=docker
uv run python main.py  # This won't see the variable!
```

---

## Environment Variable Substitution in YAML

Any YAML configuration value can use environment variables for dynamic configuration. This is useful for:

- Quick testing with different values
- Overriding configs without editing files
- Docker/production deployments

### Syntax

```yaml
# Simple substitution
bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS}"

# With default value (used if variable not set)
bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"

# Multiple variables in one string
connection_string: "kafka://${KAFKA_HOST:-localhost}:${KAFKA_PORT:-9092}"
```

### Example: Override Kafka Server On-The-Fly

In `development.yaml`:

```yaml
transport:
  kafka:
    bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
```

Then run with a different Kafka server:

```bash
# Use a different Kafka server without editing any files:
KAFKA_BOOTSTRAP_SERVERS=my-kafka:9092 uv run python main.py

# Or connect to a remote server:
KAFKA_BOOTSTRAP_SERVERS=kafka.staging.example.com:9092 uv run python main.py
```

### Common Overridable Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka connection address | `localhost:29092` |
| `KAFKA_CONSUMER_GROUP_ID` | Consumer group ID | `my-custom-group` |
| `LOG_LEVEL` | Logging level | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Component Mappings

Component mappings bridge transport-agnostic workflow definitions with Kafka-specific topics and event models. This allows workflows to reference generic component names without knowing Kafka details.

**Key Benefits:**
- Workflows remain transport-agnostic
- Easy switching between messaging systems
- Centralized transport configuration

**Quick Example:**
```yaml
# In kafka.yaml
component_mappings:
  archive_generator:
    request_topic: "archive.requests"
    response_topics:
      success: "archive.completed"
      failure: "archive.failed"

# In workflows.yaml - just reference the component
steps:
  - component: "archive_generator"  # No Kafka details needed
```

> **📖 See [Configuration Reference → Component Mappings](#component-mappings-1)** for complete settings and validation rules

---

## Logging Configuration

The application uses a **centralized logging configuration** defined in `configs/logging_config.py`.

### LOG_LEVEL Environment Variable

The `LOG_LEVEL` variable controls the logging verbosity:

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uv run python main.py

# Run with minimal logging (warnings only)
LOG_LEVEL=WARNING uv run python main.py
```

**Valid values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Default:** `INFO`

### Command Line Override

You can also pass `--log-level` as a command line argument:

```bash
uv run python main.py --log-level DEBUG
```

Note: The command line argument takes precedence over the environment variable.

### Centralized Logging Functions

All modules in the project use the centralized logging functions from `configs/logging_config.py`:

| Function | Purpose |
|----------|---------|
| `setup_logging(level)` | Initialize logging with specified level. Called once at application startup. |
| `get_logger(name)` | Get a logger instance. Use `get_logger(__name__)` in each module. |

**Example usage in a module:**

```python
from configs.logging_config import get_logger

logger = get_logger(__name__)

def my_function():
    logger.info("This is a log message")
```

### Logging Format

The default log format includes:

- Timestamp
- Logger name (module)
- Log level
- Filename and line number
- Function name
- Message

Example output:

```text
2025-12-17 09:47:39,183 - main - INFO - main.py:107 - main() - Starting application
```

### Third-Party Library Logging

The logging configuration automatically reduces noise from third-party libraries:

- `kafka` logger → `WARNING` level
- `kafka.conn` logger → `ERROR` level

---

## Environment Files

Environment-specific YAML files override default settings for different deployment scenarios.

### Available Environments

| Environment | Purpose | Common Use Case |
|-------------|---------|-----------------|
| **development** | Local development | Running on host machine with Docker Kafka |
| **docker** | Docker containers | Running orchestrator inside Docker |
| **production** | Production deployments | Production-ready settings with higher reliability |
| **testing** | Unit/integration tests | Pytest test execution (auto-detected) |

### Quick Examples

**Local Development:**
```bash
# Auto-detects development.yaml
uv run python main.py

# With debug logging
LOG_LEVEL=DEBUG uv run python main.py
```

**Docker Deployment:**
```bash
# 1. Configure environment
cp .env.example .env
# Edit .env: CONFIG_ENVIRONMENT=docker

# 2. Start services
docker compose up -d

# 3. View logs
docker compose logs -f orchestrator
```

⚠️ **Common Mistake:** Don't use `docker.yaml` on host machine - `kafka:9092` won't resolve locally!

> **📖 See [Configuration Reference → Environment File Overrides](#environment-file-overrides)** for complete environment configurations and settings

---

## Configuration Loading Process

The configuration loader follows a 4-step process:

```text
┌─────────────────────────────────────────────────────────────────┐
│  1. Load Defaults                                               │
│     ├─ app.yaml, domains.yaml, kafka.yaml, workflows.yaml      │
│     └─ Merge all default YAML files                            │
├─────────────────────────────────────────────────────────────────┤
│  2. Load Environment Overrides                                  │
│     ├─ Detect environment (CONFIG_ENVIRONMENT or auto)         │
│     └─ Deep-merge environments/{env}.yaml with defaults        │
├─────────────────────────────────────────────────────────────────┤
│  3. Expand Environment Variables                                │
│     └─ Replace ${VAR:-default} with actual values              │
├─────────────────────────────────────────────────────────────────┤
│  4. Validate with Pydantic                                      │
│     └─ Validate against ConfigDataModel in models.py           │
└─────────────────────────────────────────────────────────────────┘
```

**Later layers override earlier layers:** Environment files override defaults, and environment variables override both.

> **📖 See [Configuration Reference](#configuration-reference)** for all available settings and their validation rules

---

## Adding New Configuration

### Adding a New Environment Variable Override

1. Add `${VAR:-default}` syntax to appropriate YAML file
2. Document the variable in `.env.example`
3. Use at runtime: `VAR=value uv run python main.py`

**Example:**
```yaml
# In kafka.yaml
bootstrap_servers: "${CUSTOM_KAFKA_URL:-localhost:29092}"
```

> **📖 See [Configuration Reference → Environment Variables](#environment-variables)** for available variables

### Adding a New Environment

1. Create `configs/data/environments/{name}.yaml`
2. Add **only** values that differ from defaults (avoid duplication)
3. Activate: `CONFIG_ENVIRONMENT={name} uv run python main.py`

> **📖 See [Configuration Reference → Environment File Overrides](#environment-file-overrides)** for environment structure

### Adding a New Component Mapping

1. Add entry to `configs/data/defaults/kafka.yaml` under `component_mappings`
2. Specify request/response topics and event model names
3. Reference the component in workflow steps

> **📖 See [Configuration Reference → Component Mappings](#component-mappings-1)** for required fields

### Adding a New Workflow

1. Add workflow to `configs/data/defaults/workflows.yaml`
2. Define workflow name, description, and steps
3. Reference the workflow in `domains.yaml` if needed

> **📖 See [Configuration Reference → Workflow Settings](#workflow-settings-workflowsyaml)** for workflow structure

### Adding a New Configuration Section

For entirely new configuration sections:

1. Create `configs/data/defaults/{section}.yaml`
2. Add a Pydantic model in `configs/models.py`
3. Add the model to `ConfigDataModel`
4. Update environment files with any overrides
5. Document in Configuration Reference section

---

## Pydantic Models

The configuration is validated using Pydantic v2 models in `models.py`:

### Model Hierarchy

- `ConfigDataModel` - Root configuration
  - `AppConfig` - Application metadata
  - `TransportConfig` - Transport layer settings
    - `KafkaConfig` - Kafka-specific configuration
      - `KafkaConsumerConfig` - Consumer settings
      - `KafkaProducerConfig` - Producer settings
      - `KafkaTopicsConfig` - Orchestrator topics
      - `Dict[str, KafkaComponentMapping]` - Component mappings
  - `List[DomainConfig]` - Domain routing rules
  - `List[WorkflowConfig]` - Workflow definitions
    - `List[WorkflowStepConfig]` - Step definitions

### Type Aliases

The models use `NonEmptyStr` type alias for string fields that cannot be empty:

```python
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
```

This provides automatic validation that strings are non-empty and have whitespace stripped.

### Validation Rules

**Component Mappings:**
- `response_topics` must have `success` and `failure` keys
- `event_models` must have `request`, `success`, `failure` keys
- All values must be non-empty strings

**Workflow Steps:**
- Step names must be unique within a workflow
- `depends_on` must reference existing step names
- Circular dependencies are detected and rejected
- `timeout_seconds` must be > 0

**Workflow Configuration:**
- Workflow names must be unique across all workflows
- Each workflow must have at least one step
- Domain workflow references must point to existing workflows

**General:**
- Required field validation
- Type conversion (strings to integers, etc.)
- Cross-field validation across configuration sections

---

## Configuration Reference

This section provides a complete reference of all available configuration settings.

### Application Settings (app.yaml)

Defines application metadata and basic settings.

| Setting | Type | Default | Required | Description |
|---------|------|---------|----------|-------------|
| `app.name` | string | `civers_orchestrator` | Yes | Application name for identification |
| `app.version` | string | `1.0.0` | Yes | Application version |
| `app.environment` | string | `development` | Yes | Runtime environment identifier |

**Example:**
```yaml
app:
  name: civers_orchestrator
  version: 1.0.0
  environment: development
```

---

### Transport Settings (kafka.yaml)

Defines message transport configuration, currently supporting Kafka.

#### Transport Layer

| Setting | Type | Default | Required | Description |
|---------|------|---------|----------|-------------|
| `transport.enabled` | list[string] | `["kafka"]` | Yes | List of enabled transport mechanisms |

#### Kafka Connection

| Setting | Type | Default | Required | Description |
|---------|------|---------|----------|-------------|
| `transport.kafka.bootstrap_servers` | string | `localhost:29092` | Yes | Kafka broker addresses (comma-separated for multiple) |

**Environment Variable:** Can use `${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}` for dynamic configuration.

#### Kafka Consumer

| Setting | Type | Default | Required | Description |
|---------|------|---------|----------|-------------|
| `transport.kafka.consumer.group_id` | string | `civers_orchestrator` | Yes | Consumer group ID for Kafka consumer |
| `transport.kafka.consumer.auto_offset_reset` | string | `earliest` | Yes | Offset reset policy (`earliest`, `latest`, `none`) |

**Environment Variable:** Can use `${KAFKA_CONSUMER_GROUP_ID:-civers_orchestrator}` for dynamic configuration.

#### Kafka Producer

| Setting | Type | Default | Required | Description |
|---------|------|---------|----------|-------------|
| `transport.kafka.producer.acks` | string | `all` | Yes | Acknowledgment policy (`0`, `1`, `all`) |
| `transport.kafka.producer.retries` | int | `3` | Yes | Number of retries for failed sends |

#### Kafka Topics (Orchestrator)

Topics for orchestrator-to-external communication.

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `transport.kafka.topics.orchestrator_requests` | string | Yes | Topic for incoming workflow requests |
| `transport.kafka.topics.orchestrator_status` | string | Yes | Topic for workflow status updates |
| `transport.kafka.topics.orchestrator_completed` | string | Yes | Topic for completed workflows |
| `transport.kafka.topics.orchestrator_failed` | string | Yes | Topic for failed workflows |

**Default Values:**
```yaml
topics:
  orchestrator_requests: "orchestrator.requests"
  orchestrator_status: "orchestrator.status"
  orchestrator_completed: "orchestrator.completed"
  orchestrator_failed: "orchestrator.failed"
```

#### Component Mappings

Maps component IDs to Kafka topics and event model classes. Each component mapping requires:

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `request_topic` | string | Yes | Kafka topic for component requests |
| `response_topics.success` | string | Yes | Kafka topic for successful completions |
| `response_topics.failure` | string | Yes | Kafka topic for failures |
| `event_models.request` | string | Yes | Event model class name for requests |
| `event_models.success` | string | Yes | Event model class name for success |
| `event_models.failure` | string | Yes | Event model class name for failure |

**Validation:**
- `response_topics` must have both `success` and `failure` keys
- `event_models` must have `request`, `success`, and `failure` keys
- All values must be non-empty strings

**Example:**
```yaml
component_mappings:
  archive_generator:
    request_topic: "archive.requests"
    response_topics:
      success: "archive.completed"
      failure: "archive.failed"
    event_models:
      request: "ArchiveRequestEvent"
      success: "ArchiveCompletedEvent"
      failure: "ArchiveFailedEvent"
```

---

### Domain Settings (domains.yaml)

Maps URL domains to workflow names for routing.

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `domains[].name` | string | Yes | Domain name (supports wildcards with `*`) or `"default"` |
| `domains[].workflow` | string | Yes | Workflow name to execute (must exist in workflows.yaml) |

**Matching Priority:**
1. Exact domain match (e.g., `arachne.dainst.org`)
2. Wildcard match (e.g., `*.dainst.org`)
3. Default fallback (`name: "default"`)

**Validation:**
- Domain names cannot be empty
- Workflow references must point to existing workflows

**Example:**
```yaml
domains:
  - name: "arachne.dainst.org"
    workflow: "archaeology_workflow"

  - name: "*.dainst.org"
    workflow: "dainst_default_workflow"

  - name: "default"
    workflow: "standard_archive_workflow"
```

---

### Workflow Settings (workflows.yaml)

Defines workflow structures and step configurations.

#### Workflow Configuration

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `workflows[].name` | string | Yes | Unique workflow name |
| `workflows[].description` | string | Yes | Human-readable workflow description |
| `workflows[].steps` | list | Yes | List of workflow steps (at least one required) |

**Validation:**
- Workflow names must be unique across all workflows
- Each workflow must have at least one step

#### Workflow Step Configuration

Each step in `workflows[].steps` requires:

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `name` | string | Yes | Unique step name within workflow |
| `component` | string | Yes | Component identifier (must exist in component_mappings) |
| `input_schema` | string | Yes | Input data schema name |
| `output_schemas.success` | string | Yes | Success output schema name |
| `output_schemas.failure` | string | Yes | Failure output schema name |
| `depends_on` | list[string] | No | List of step names this step depends on (empty list = no dependencies) |
| `timeout_seconds` | int | Yes | Step timeout in seconds (must be > 0) |

**Validation:**
- Step names must be unique within the workflow
- `depends_on` must reference existing step names in the same workflow
- Circular dependencies are not allowed
- `timeout_seconds` must be a positive integer

**Example:**
```yaml
workflows:
  - name: "archaeology_workflow"
    description: "Workflow for archaeological content archiving"
    steps:
      - name: "archive_generation"
        component: "archive_generator"
        input_schema: "ArchiveRequest"
        output_schemas:
          success: "ArchiveCompleted"
          failure: "ArchiveFailed"
        depends_on: []
        timeout_seconds: 300

      - name: "metadata_extraction"
        component: "metadata_extractor"
        input_schema: "MetadataRequest"
        output_schemas:
          success: "MetadataCompleted"
          failure: "MetadataFailed"
        depends_on: ["archive_generation"]
        timeout_seconds: 120
```

---

### Environment File Overrides

Environment-specific files override default values. Only include settings that differ from defaults.

#### Development Environment (development.yaml)

**Purpose:** Local development on host machine

**Common Overrides:**
```yaml
app:
  environment: development

transport:
  kafka:
    bootstrap_servers: "localhost:29092"
```

#### Docker Environment (docker.yaml)

**Purpose:** Running inside Docker containers

**Common Overrides:**
```yaml
app:
  environment: docker

transport:
  kafka:
    bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
```

#### Production Environment (production.yaml)

**Purpose:** Production deployments with enhanced reliability

**Common Overrides:**
```yaml
app:
  environment: production

transport:
  kafka:
    bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS}"  # No default - must be set
    consumer:
      group_id: "civers_orchestrator_prod"
    producer:
      retries: 5  # Higher retry count
```

#### Testing Environment (testing.yaml)

**Purpose:** Unit and integration tests

**Common Overrides:**
```yaml
app:
  environment: testing

transport:
  kafka:
    bootstrap_servers: "localhost:29093"  # Isolated test broker
    consumer:
      group_id: "civers_orchestrator_test"
```

---

### Environment Variables

The following environment variables can be used to override configuration:

| Variable | Used In | Purpose | Example |
|----------|---------|---------|---------|
| `CONFIG_ENVIRONMENT` | Loader | Select environment file | `development`, `docker`, `production`, `testing` |
| `LOG_LEVEL` | Logging | Set logging level | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KAFKA_BOOTSTRAP_SERVERS` | kafka.yaml | Kafka broker addresses | `localhost:29092` |
| `KAFKA_CONSUMER_GROUP_ID` | kafka.yaml | Consumer group ID | `my-custom-group` |

**Usage Pattern:**
```yaml
# In YAML file
bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"
```

```bash
# Override at runtime
KAFKA_BOOTSTRAP_SERVERS=kafka.prod:9092 uv run python main.py
```

---

## Troubleshooting

### Check Which Environment is Detected

```bash
uv run python -c "
from configs.loaders import YamlFileConfigLoader
loader = YamlFileConfigLoader()
print(f'Environment: {loader.environment}')
"
```

### Environment Variable Not Expanding

```bash
# Verify the variable is set
echo $KAFKA_BOOTSTRAP_SERVERS

# Check if it's being passed to the container
docker compose exec orchestrator env | grep KAFKA
```

### Validation Errors

```bash
uv run python -c "
from configs.loaders import YamlFileConfigLoader
loader = YamlFileConfigLoader()
try:
    config = loader.load()
    print('✅ Configuration valid')
except Exception as e:
    print(f'❌ Validation error: {e}')
"
```

### View Complete Merged Configuration

```bash
uv run python -c "
from configs.loaders import YamlFileConfigLoader
import json

loader = YamlFileConfigLoader()
config = loader.load()
print(json.dumps(config.model_dump(), indent=2))
"
```
