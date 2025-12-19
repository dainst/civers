# CiVers Orchestrator - Testing Guide

Complete testing guide for the CiVers Orchestrator project.

## Quick Start

```bash
# Run all tests (Kafka auto-starts if needed)
uv run pytest

# Run only unit tests (fast, no Kafka needed)
uv run pytest tests/unit/ -v

# Run only integration tests (Kafka auto-starts)
uv run pytest tests/integration/ -v

# Run only E2E tests (real services + background mocks)
uv run pytest tests/e2e/ -v -s

# Run with coverage report
uv run pytest --cov=orchestration_services --cov=transport_services --cov-report=term-missing
```

## Table of Contents

1. [Test Structure](#test-structure)
2. [Configuration](#configuration)
3. [Auto-Start Kafka](#auto-start-kafka)
4. [Unit Tests](#unit-tests)
5. [Integration Tests](#integration-tests)
6. [End-to-End (E2E) Tests](#end-to-end-e2e-tests)
7. [Shared Fixtures](#shared-fixtures)
8. [Writing Tests](#writing-tests)
9. [Troubleshooting](#troubleshooting)

---

## Test Structure

```text
tests/
├── conftest.py              # Shared fixtures (test_config, orchestrator)
├── unit/                    # Unit tests (no external dependencies)
│   ├── test_orchestrator_service.py
│   ├── test_config_loader.py
│   └── ...
├── integration/             # Integration tests (with real Kafka)
│   ├── conftest.py          # Integration fixtures + auto-start Kafka
│   ├── test_kafka_integration.py
│   └── test_workflow_orchestration.py
├── e2e/                     # End-to-End tests (Full event loop)
│   ├── conftest.py          # E2E fixtures (LiveService, MockComponents)
│   └── test_workflow_e2e.py # Full workflow tests
└── README.md                # This file
```

### Test Categories

| Category | Location | Dependencies | Speed | Purpose |
|----------|----------|--------------|-------|---------|
| **Unit** | `tests/unit/` | None (mocked) | Fast | Test individual components |
| **Integration** | `tests/integration/` | Real Kafka | Medium | Test component interactions & transport |
| **E2E** | `tests/e2e/` | Real Kafka + Real Service | Slow | Test complete event loop & workflow data |

---

## Configuration

All tests use [configs/data/environments/testing.yaml](../configs/data/environments/testing.yaml) as the **single source of truth** for configuration.

### How Configuration Works

1. **Auto-detection**: The `force_testing_environment()` fixture in [tests/conftest.py](conftest.py) automatically sets `CONFIG_ENVIRONMENT=testing`
2. **Config loading**: Tests use `test_config` fixture which loads from `testing.yaml`
3. **Test topics**: All Kafka topics use `test.*` prefix to avoid production conflicts
4. **Test workflows**: Simplified workflows (no DOI assignment) for faster tests

### Configuration Features

```yaml
# testing.yaml highlights
app:
  environment: testing
  name: "civers-orchestrator-test"

transport:
  kafka:
    bootstrap_servers: "localhost:29092"
    topics:
      orchestrator_requests: "test.orchestrator.requests"
      # All topics prefixed with "test."

    component_mappings:
      archive_generator:
        request_topic: "test.archive.requests"
        # Component → topic mappings for tests

workflows:
  - name: "simple_workflow"      # Single-step for basic tests
  - name: "archaeology_workflow"  # Two-step with dependency
  - name: "dainst_workflow"       # DAINST default workflow
```

### Using Configuration in Tests

```python
# Option 1: Use test_config fixture
def test_something(test_config):
    assert test_config.app.environment == "testing"
    assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"

# Option 2: Use orchestrator fixture (includes config)
def test_workflow(orchestrator):
    instruction = orchestrator.start_workflow(
        request_id="test-001",
        url="https://example.com"
    )
    assert instruction is not None

# Option 3: Load directly (rare)
from configs.loaders import YamlFileConfigLoader
config = YamlFileConfigLoader().load()  # Auto-loads testing.yaml
```

**Benefits:**

- ✅ Single source of truth
- ✅ Easy to update (change once, affects all tests)
- ✅ No hardcoded configurations
- ✅ Consistent across all tests

---

## Auto-Start Kafka

Integration tests **automatically start and stop Kafka** using Docker Compose. No manual setup required!

### How It Works

1. **Auto-start enabled by default**: The `auto_start_kafka` fixture runs before integration tests
2. **Starts Kafka**: Runs `docker compose up -d kafka`
3. **Health check**: Waits for Kafka to be fully ready (max 60 seconds)
4. **Runs tests**: All integration tests execute with real Kafka
5. **Auto-cleanup**: Stops Kafka with `docker compose down kafka` after tests

### Usage Examples

**Default: Fully automatic**

```bash
# Kafka starts automatically - no manual setup!
uv run pytest tests/integration/ -v
```

**Disable auto-start (use manually started Kafka)**

```bash
# Start Kafka manually
docker compose up -d kafka

# Run tests without auto-start
AUTO_START_KAFKA=false uv run pytest tests/integration/ -v

# Stop Kafka manually when done
docker compose down kafka
```

**Custom timeout for slow systems**

```bash
KAFKA_STARTUP_TIMEOUT=120 uv run pytest tests/integration/ -v
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_START_KAFKA` | `true` | Enable/disable auto-start |
| `KAFKA_STARTUP_TIMEOUT` | `60` | Max seconds to wait for startup |

### Requirements

- **Docker Compose** 2.0+ installed and running
- **docker-compose.yml** in project root
- Sufficient system resources for Kafka container

### Health Check

The auto-start fixture performs comprehensive checks:

1. **Socket check**: Verifies port 29092 is open
2. **Broker check**: Connects with Kafka client
3. **API version**: Confirms broker is initialized
4. **Topic listing**: Verifies broker is ready for operations

---

## Unit Tests

Located in [tests/unit/](unit/). Fast tests with no external dependencies.

### Characteristics

- ✅ No external services required
- ✅ Use mocks for dependencies
- ✅ Fast execution (< 1 second per test)
- ✅ Test individual functions/classes in isolation

### Key Test Files

| File | Tests |
|------|-------|
| [test_orchestrator_service.py](unit/test_orchestrator_service.py) | OrchestratorService facade |
| [test_workflow_state_store.py](unit/test_workflow_state_store.py) | Workflow state management |
| [test_step_executor.py](unit/test_step_executor.py) | Step execution logic |
| [test_config_loader.py](unit/test_config_loader.py) | Configuration loading |
| [test_testing_config_loading.py](unit/test_testing_config_loading.py) | testing.yaml validation |
| [test_component_mappings_config.py](unit/test_component_mappings_config.py) | Kafka component mappings |

### Running Unit Tests

```bash
# All unit tests
uv run pytest tests/unit/ -v

# Specific test file
uv run pytest tests/unit/test_orchestrator_service.py -v

# Specific test function
uv run pytest tests/unit/test_orchestrator_service.py::test_start_workflow -v

# With coverage
uv run pytest tests/unit/ --cov=orchestration_services --cov-report=term-missing
```

### Example Unit Test

```python
def test_workflow_domain_matching_exact(orchestrator):
    """Test exact domain matching for workflow selection."""
    # Arrange - orchestrator fixture provides initialized service

    # Act - start workflow with arachne domain
    instruction = orchestrator.start_workflow(
        request_id="test-123",
        url="https://arachne.dainst.org/entity/123"
    )

    # Assert - should match archaeology_workflow
    state = orchestrator.get_workflow_state("test-123")
    assert state.workflow_name == "archaeology_workflow"
    assert instruction.component == "archive_generator"
```

---

## Integration Tests

Located in [tests/integration/](integration/). Tests with real Kafka infrastructure.

### Characteristics

- ✅ Test component interactions
- ✅ Use real Kafka broker (auto-started)
- ✅ Test end-to-end workflows
- ✅ Verify transport layer

### Key Test Files

| File | Tests |
|------|-------|
| [test_workflow_orchestration.py](integration/test_workflow_orchestration.py) | Complete workflow execution |
| [test_kafka_integration.py](integration/test_kafka_integration.py) | Kafka transport integration |

### Running Integration Tests

```bash
# All integration tests (Kafka auto-starts)
uv run pytest tests/integration/ -v

# Specific test class
uv run pytest tests/integration/test_kafka_integration.py::TestKafkaIntegrationBasic -v

# Skip Kafka auto-start (if Kafka already running)
AUTO_START_KAFKA=false uv run pytest tests/integration/ -v

# With custom Kafka startup timeout
KAFKA_STARTUP_TIMEOUT=120 uv run pytest tests/integration/ -v
```

### Example Integration Test

```python
@pytest.mark.asyncio
async def test_complete_workflow_execution(orchestrator):
    """Test complete workflow from start to finish."""
    # Start workflow
    instruction = orchestrator.start_workflow(
        request_id="test-workflow-001",
        url="https://example.com"
    )

    # Verify initial step
    assert instruction.component == "archive_generator"

    # Simulate step completion
    transition = orchestrator.step_completed(
        request_id="test-workflow-001",
        step_name="archive_generation",
        result={"archive_url": "s3://bucket/archive.zip"}
    )

    # Verify workflow completed
    assert transition.action == "workflow_completed"
```

---

## End-to-End (E2E) Tests

Located in [tests/e2e/](e2e/). Full system tests running the real service against background mock components.

### Characteristics

- ✅ **Real Event Loop**: Runs the actual `KafkaTransportService` in a background task.
- ✅ **Mock Components**: Simulates external services (Archive Generator, Metadata Extractor) that respond to Kafka events.
- ✅ **Workflow Validation**: Verifies that the Orchestrator correctly routes data (e.g., `snapshot_id`) between steps.
- ✅ **Configuration Driven**: Uses `testing.yaml` as the map for all topic and component mappings.

### Running E2E Tests

```bash
# Run all E2E tests (Kafka auto-starts)
uv run pytest tests/e2e/ -v -s

# Run specifically the archaeology workflow test
uv run pytest tests/e2e/test_workflow_e2e.py::test_archaeology_workflow_e2e -v -s
```

### Core Fixtures

- `live_kafka_service`: Spins up the real orchestrator + Kafka transport in the background.
- `create_mock_component`: Factory to create a `MockComponent` that simulates a specific service (e.g., `archive_generator`).
- `e2e_test_driver`: Acts as the external caller, submitting requests and waiting for final `completed` events.

### Example E2E Test

```python
async def test_archaeology_workflow(live_kafka_service, create_mock_component, e2e_test_driver):
    # 1. Setup mock services
    await create_mock_component("archive_generator")
    await create_mock_component("metadata_extractor")

    # 2. Submit real Kafka request
    await e2e_test_driver.send_request(url="https://example.com", request_id="e2e-123")

    # 3. Wait for final orchestrator result
    result = await e2e_test_driver.wait_for_result("e2e-123")
    assert result["workflow_name"] == "archaeology_workflow"
```

---

## Shared Fixtures

Common fixtures available to all tests via [tests/conftest.py](conftest.py).

### Available Fixtures

#### `test_config` (session-scoped)

Loads configuration from testing.yaml.

```python
def test_kafka_config(test_config):
    assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"
    assert test_config.app.environment == "testing"
```

#### `orchestrator` (function-scoped)

Provides initialized OrchestratorService.

```python
def test_start_workflow(orchestrator):
    instruction = orchestrator.start_workflow(
        request_id="test-001",
        url="https://example.com"
    )
    assert instruction is not None
```

#### `force_testing_environment` (session-scoped, autouse)

Automatically sets `CONFIG_ENVIRONMENT=testing` for all tests.

### Integration-Specific Fixtures

From [tests/integration/conftest.py](integration/conftest.py):

- `auto_start_kafka`: Automatically starts/stops Kafka (session-scoped)
- `kafka_available`: Verifies Kafka is ready
- `integration_kafka_config`: Loads test configuration
- `kafka_admin_client`: Admin client for topic management
- `kafka_transport_service`: Initialized KafkaTransportService
- `mock_orchestrator_service`: Mock orchestrator for transport tests

---

## Writing Tests

### Naming Conventions

```python
# Test files
test_<module_name>.py

# Test classes (optional, for grouping)
class Test<ComponentName>:
    ...

# Test functions
def test_<what_is_tested>_<expected_behavior>():
    ...
```

### Test Structure (AAA Pattern)

```python
def test_step_completed_transitions_to_next_step(orchestrator):
    """When a step completes, orchestrator should transition to next step."""

    # Arrange - Set up test conditions
    orchestrator.start_workflow("req-1", "https://example.com")

    # Act - Perform the action being tested
    transition = orchestrator.step_completed("req-1", "archive_generation")

    # Assert - Verify expected outcomes
    assert transition.action == "execute_step"
    assert transition.step_instruction.component == "metadata_extractor"
```

### Best Practices

✅ **DO:**

- Use descriptive test names that explain what is tested
- Test one thing per test function
- Use fixtures for common setup
- Keep tests independent (no shared state)
- Use `test_config` fixture instead of hardcoding
- Mock external dependencies in unit tests
- Use real services in integration tests

❌ **DON'T:**

- Hardcode configuration values
- Create `ConfigDataModel()` manually
- Share state between tests
- Test multiple behaviors in one test
- Skip writing tests for complex logic

### Example: Good vs Bad

```python
# ❌ BAD - Hardcoded configuration
def test_kafka_config():
    config = ConfigDataModel(
        app=AppConfig(name="test", ...),  # 50+ lines of hardcoding
        transport=TransportConfig(...)
    )
    assert config.transport.kafka.bootstrap_servers == "localhost:29092"

# ✅ GOOD - Use test_config fixture
def test_kafka_config(test_config):
    assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"
```

### Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.integration
def test_kafka_transport():
    """Integration test requiring Kafka."""
    pass

@pytest.mark.kafka
def test_kafka_specific_feature():
    """Test specifically for Kafka functionality."""
    pass
```

Run specific markers:

```bash
# Run only integration tests
uv run pytest -m integration

# Skip integration tests
uv run pytest -m "not integration"
```

---

## Troubleshooting

### Common Issues

#### 1. Kafka Not Starting

**Symptom:**

```text
ERROR: Kafka did not become healthy within 60s
```

**Solutions:**

- Increase timeout: `KAFKA_STARTUP_TIMEOUT=120 uv run pytest tests/integration/`
- Check Docker is running: `docker ps`
- Check Docker resources (memory, CPU)
- View Kafka logs: `docker compose logs kafka`
- Try manual start: `docker compose up -d kafka`

#### 2. Port Already in Use

**Symptom:**

```text
ERROR: Bind for 0.0.0.0:29092 failed: port is already allocated
```

**Solutions:**

- Stop existing Kafka: `docker compose down kafka`
- Check other processes: `lsof -i :29092`
- Disable auto-start: `AUTO_START_KAFKA=false uv run pytest tests/integration/`

#### 3. Config Not Loading

**Symptom:**

```text
AssertionError: assert 'docker' == 'testing'
```

**Solutions:**

- Verify `force_testing_environment` fixture is active
- Check `CONFIG_ENVIRONMENT` is not set externally
- Ensure pytest is being used (not `python` directly)

#### 4. Test Failures After Config Changes

**Symptom:**

```text
AssertionError: assert 'archive.requests' == 'test.archive.requests'
```

**Solutions:**

- Update test assertions to match testing.yaml
- Check if test is using hardcoded values instead of fixtures
- Verify testing.yaml has correct values

#### 5. Import Errors

**Symptom:**

```text
ModuleNotFoundError: No module named 'orchestration_services'
```

**Solutions:**

- Run tests via `uv run pytest` (not `python -m pytest`)
- Ensure you're in project root directory
- Check dependencies are installed: `uv sync`

### Debug Commands

```bash
# Run tests with verbose output and show print statements
uv run pytest -v -s

# Run tests with full traceback
uv run pytest --tb=long

# Run tests with pdb on failure
uv run pytest --pdb

# List all available fixtures
uv run pytest --fixtures

# Show test collection without running
uv run pytest --collect-only

# Run specific test with maximum verbosity
uv run pytest tests/unit/test_orchestrator_service.py::test_start_workflow -vv
```

### Performance

- **Unit tests**: ~0.1-0.5 seconds each
- **Integration tests**: ~2-10 seconds each (includes Kafka operations)
- **Kafka startup**: ~4-6 seconds (session-scoped, runs once)

For faster local development:

```bash
# Keep Kafka running between test runs
docker compose up -d kafka

# Run tests without auto-start overhead
AUTO_START_KAFKA=false uv run pytest tests/integration/ -v
```

---

## Test Statistics

Current test coverage:

```
Tests:        ~270 total
  Unit:       242 tests
  Integration: 22 tests
  E2E:         2 tests
  Passed:      ✅ 100%

Coverage:
  orchestration_services: 95%+
  transport_services:     90%+
  configs:                85%+
```

---

## CI/CD Integration

Integration tests work seamlessly in CI/CD pipelines:

```yaml
# .github/workflows/test.yml (example)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync

      - name: Run unit tests
        run: uv run pytest tests/unit/ -v

      - name: Run integration tests (Kafka auto-starts)
        run: uv run pytest tests/integration/ -v

      - name: Upload coverage
        run: uv run pytest --cov --cov-report=xml
```

No additional CI configuration needed - auto-start Kafka handles everything!

---

## Related Documentation

- **[../TESTING_GUIDE.md](../TESTING_GUIDE.md)** - Original testing guide (comprehensive)
- **[../TEST_CONFIGURATION_GUIDE.md](../TEST_CONFIGURATION_GUIDE.md)** - Configuration migration guide
- **[../KAFKA_INTEGRATION_GUIDE.md](../KAFKA_INTEGRATION_GUIDE.md)** - Kafka architecture details
- **[../configs/README.md](../configs/README.md)** - Configuration system overview
- **[integration/README.md](integration/README.md)** - Integration testing detailed guide
- **[../docker-compose.yml](../docker-compose.yml)** - Docker services configuration

---

## Quick Reference Card

```bash
# === Common Commands ===

# Run all tests
uv run pytest

# Run only unit tests (fast)
uv run pytest tests/unit/

# Run only integration tests (Kafka auto-starts)
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov --cov-report=term-missing

# === Environment Variables ===

# Disable Kafka auto-start
AUTO_START_KAFKA=false uv run pytest tests/integration/

# Custom Kafka timeout
KAFKA_STARTUP_TIMEOUT=120 uv run pytest tests/integration/

# === Markers ===

# Run only integration tests
uv run pytest -m integration

# Skip integration tests
uv run pytest -m "not integration"

# === Debugging ===

# Verbose with print statements
uv run pytest -v -s

# Debug on failure
uv run pytest --pdb

# Show fixtures
uv run pytest --fixtures

# === Manual Kafka Management ===

# Start Kafka manually
docker compose up -d kafka

# Stop Kafka manually
docker compose down kafka

# View Kafka logs
docker compose logs -f kafka
```

---

**Last Updated**: 2025-12-18
**Test Framework**: pytest 8.3.5
**Python Version**: 3.12+
**Kafka Auto-Start**: ✅ Enabled by default
