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

# Legacy directories (will be cleaned up)
├── configs/                        # OLD - moved to unit/configs/
├── kafka_layer/                    # OLD - split between unit/ and integration/
├── services/                       # OLD - moved to unit/services/
├── storage/                        # OLD - moved to unit/storage/
└── Integration_tests/              # OLD - moved to integration/
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

### Quick Commands

```bash
# Run all unit tests (fast)
./run_tests.sh unit

# Run all integration tests (slow, requires Docker)
./run_tests.sh integration

# Run specific test categories
./run_tests.sh kafka
./run_tests.sh e2e

# Run all tests
./run_tests.sh all

# Generate coverage report
./run_tests.sh coverage
```

### Manual pytest Commands

```bash
# Unit tests only
pytest tests/unit/ -m "unit" -v

# Integration tests only  
pytest tests/integration/ -m "integration" -v

# Specific markers
pytest -m "kafka" -v
pytest -m "unit and not slow" -v

# With coverage
pytest --cov=. --cov-report=html tests/
```

## 🎯 **Test Categories**

### **Unit Tests** (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (< 1 second per test)
- **Dependencies**: None (uses mocks)
- **Examples**: Data model validation, configuration parsing, isolated service logic

### **Integration Tests** (`tests/integration/`)
- **Purpose**: Test component interactions with real services
- **Speed**: Slow (5-30 seconds per test)
- **Dependencies**: Docker, Kafka, browsers
- **Examples**: Kafka producer-consumer workflows, database interactions, API calls

### **End-to-End Tests** (`tests/integration/end_to_end/`)
- **Purpose**: Test complete user workflows
- **Speed**: Very slow (30+ seconds per test)
- **Dependencies**: All external services
- **Examples**: Complete archive generation workflows, multi-service interactions

## 🔧 **Shared Fixtures**

Located in `tests/fixtures/shared_fixtures.py`:

- `config`: Loads test configuration
- `config_with_temp_dir`: Configuration with temporary archive directory
- `temp_archive_dir`: Temporary directory for test files
- `kafka_container`: Docker Kafka container for integration tests
- `mock_config`: Mock configuration for unit tests

## 📋 **Test Writing Guidelines**

### **Unit Tests**
```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
def test_component_logic(mock_config):
    # Test isolated component logic
    pass
```

### **Integration Tests**
```python
import pytest

@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
async def test_kafka_integration(config, kafka_container):
    # Test with real Kafka
    pass
```

### **End-to-End Tests**
```python
import pytest

@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_complete_workflow(config, kafka_container, temp_archive_dir):
    # Test complete workflow
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
- [x] Created new directory structure
- [x] Set up pytest configuration
- [x] Created shared fixtures
- [x] Moved unit tests to `tests/unit/`
- [x] Moved integration tests to `tests/integration/`
- [x] Created test runner scripts
- [x] Updated current integration test

### 🔄 **In Progress**
- [ ] Update import paths in moved tests
- [ ] Add missing test markers
- [ ] Clean up old test directories

### 📅 **Next Steps**
- [ ] Remove old test directories after verification
- [ ] Add more comprehensive integration tests
- [ ] Set up CI/CD pipeline with new structure
- [ ] Add performance benchmarking tests

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
