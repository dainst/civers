# Test Organization Documentation

## 📁 **Test Directory Structure**

```
tests/
├── unit/                           # Fast unit tests (no external dependencies)
│   ├── configs/                    # Configuration-related tests
│   ├── kafka_layer/                # Kafka layer unit tests with mocks
│   ├── services/                   # Service layer unit tests
│   ├── archive_generators/         # Archive generator unit tests
│   └── storage/                    # Storage layer unit tests
├── integration/                    # Integration tests (require external services)
│   ├── kafka/                      # Kafka integration tests
│   ├── playwright/                 # Browser integration tests
│   └── end_to_end/                 # Complete workflow tests
├── fixtures/                       # Shared test fixtures and utilities
│   ├── __init__.py
│   └── shared_fixtures.py          # Common fixtures for all tests
└── conftest.py                     # Main pytest configuration
```

## 🏷️ **Test Markers**

| Marker | Description | Speed | Dependencies |
|--------|-------------|-------|--------------|
| `@pytest.mark.unit` | Fast unit tests with mocks | ⚡ Fast | None |
| `@pytest.mark.integration` | Tests requiring external services | 🐌 Slow | Docker, Kafka |
| `@pytest.mark.kafka` | Kafka-specific tests | 🐌 Slow | Kafka broker |
| `@pytest.mark.playwright` | Browser automation tests | 🐌 Slow | Browser, network |
| `@pytest.mark.e2e` | End-to-end workflow tests | 🐌 Very slow | All services |
| `@pytest.mark.slow` | Tests taking >5 seconds | 🐌 Slow | Varies |
| `@pytest.mark.docker` | Tests requiring Docker | 🐌 Slow | Docker |

## 🚀 **Running Tests**

### Manual pytest Commands (Recommended)

```bash
# Run all unit tests (fast)
uv run pytest tests/unit/ -v

# Run unit tests with specific marker
uv run pytest tests/unit/ -m "unit" -v

# Run integration tests (requires Docker/Kafka)
uv run pytest tests/integration/ --run-integration -v

# With coverage
uv run pytest tests/unit/ --cov=. --cov-report=html
```

> [!IMPORTANT]
> The legacy `./run_tests.sh` script is deprecated. Use `uv run pytest` directly for better control.

## 🎯 **Test Categories**

### **Unit Tests** (`tests/unit/`)

- **Purpose**: Test individual modules in isolation with mocks.
- **Speed**: Pure Python, ultra-fast.
- **Markers**: `@pytest.mark.unit`

### **Integration & E2E Tests** (Monorepo)

Most long-running tests requiring Docker, Kafka, or browser infrastructure are being migrated to the **monorepo** at `civers/tests/integration/` to ensure full-stack consistency.

Integrated tests still residing in this repo:

- `tests/integration/test_complete_integration.py` (Fast component-level integration)
- `tests/integration/test_fast.py` (Quick infrastructure checks)

## 🔧 **Shared Fixtures**

Located in `tests/fixtures/shared_fixtures.py`:

- `config`: Loads test configuration
- `temp_archive_dir`: Temporary directory for test files
- `mock_config`: Comprehensive mock configuration for unit tests
- `sample_config`: Lightweight mock config for simple tests

## 📋 **Test Writing Guidelines**

### **Unit Tests**

```python
import pytest
from unittest.mock import Mock, patch

pytestmark = [pytest.mark.unit]

def test_component_logic(mock_config):
    # Test isolated component logic
    pass
```

## 🚦 **CI/CD Integration**

### Recommended CI Pipeline

```yaml
# Fast feedback loop
- name: Unit Tests
  run: ./run_tests.sh unit
  
# Slower integration tests
- name: Integration Tests  
  run: ./run_tests.sh integration
  
# Full test suite with coverage
- name: Coverage Report
  run: ./run_tests.sh coverage
```

## 🧹 **Migration Status**

### ✅ **Completed**

- [x] Unified marker definitions in `pytest.ini`
- [x] Cleaned up `conftest.py` duplication
- [x] Standardized `@pytest.mark.unit` usage across all files
- [x] Moved unit tests to tiered directory structure
- [x] Identified integration/e2e candidates for monorepo migration

### 🔄 **In Progress**

- [/] Migrating long-running tests to monorepo
- [/] Updating main README documentation

### 📅 **Next Steps**

- [ ] Finalize monorepo test infrastructure
- [ ] Remove Docker-dependent tests from this repository after migration
- [ ] Set up unified CI pipeline for the monorepo

## 🆘 **Common Issues & Solutions**

### Import Errors

```bash
# If you see import errors, make sure the project root is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Docker Issues

```bash
# Start Kafka container manually if needed
docker-compose -f tests/test-docker-compose.yml up -d test-broker
```

### Missing Dependencies

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-timeout
```

## 🐳 **Unified Docker Fixtures** (NEW)

All integration tests now use unified Docker fixtures defined in `tests/fixtures/docker_fixtures.py` for consistent container management.

### Available Fixtures

#### `test_kafka_only`

- **Purpose**: Ultra-fast tests with isolated test Kafka
- **Containers**: test-broker (Kafka on port 29093)
- **Use Case**: Quick Kafka connectivity tests (15 seconds)
- **Config**: Uses `tests/test-docker-compose.yml`

#### `main_kafka_only`

- **Purpose**: Production-like Kafka testing without archive processing
- **Containers**: broker (Kafka on port 29092), kafka-ui (port 8089)
- **Use Case**: Kafka message flow tests
- **Config**: Uses main `docker-compose.yml`

#### `full_stack`

- **Purpose**: Complete end-to-end integration testing
- **Containers**: broker, kafka-ui, archive-generator
- **Use Case**: Full archive generation pipeline tests
- **Config**: Uses main `docker-compose.yml`

#### `reuse_containers`

- **Purpose**: Development mode - reuses existing containers
- **Containers**: Reuses whatever is already running
- **Use Case**: Development and debugging
- **Config**: Minimal setup, no teardown

### Usage Examples

```python
def test_fast_kafka_publishing(test_kafka_only):
    """Ultra-fast test using isolated test Kafka."""
    # Test with test-broker on port 29093
    pass

def test_kafka_message_flow(main_kafka_only):
    """Test Kafka without archive processing."""
    # Test with production broker on port 29092
    pass

def test_full_archive_generation(full_stack):
    """Complete end-to-end test with archive generation."""
    # Test full pipeline including archive generation
    pass

def test_during_development(reuse_containers):
    """Development test that reuses existing containers."""
    # Useful when containers are already running
    pass
```

### Performance Guidelines

- Use `test_kafka_only` for quick tests (~15 seconds)
- Use `main_kafka_only` for Kafka-focused tests (~30 seconds)
- Use `full_stack` for comprehensive tests (~60+ seconds)
- Use `reuse_containers` during development to avoid startup overhead

**⚠️ IMPORTANT**: All tests in the same test file should use the same fixture type to avoid container restart delays. Mixed fixtures (e.g., `full_stack` + `main_kafka_only`) will cause 3+ minute delays as containers are torn down and restarted between tests.

**✅ Good** (fast):

```python
def test_one(full_stack): pass
def test_two(full_stack): pass
```

**❌ Bad** (3+ minute delay):

```python
def test_one(full_stack): pass  
def test_two(main_kafka_only): pass  # Causes restart!
```

### Migration from Old Fixtures

The unified system replaces several old approaches:

- ❌ `compose_up` fixture in `test_docker_compose.py` (removed)
- ❌ `quick_compose` fixture (removed)
- ❌ `kafka_ready` fixture (removed)
- ❌ Custom Docker setup in `test_fast.py` (removed)
- ❌ `test_kafka_only.py` file (consolidated into `test_kafka_core.py`)

All tests now use the unified fixtures for consistency and maintainability.
