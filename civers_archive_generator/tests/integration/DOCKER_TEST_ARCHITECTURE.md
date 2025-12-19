# Docker Test Architecture

## Overview

The integration tests now use a **dedicated test environment** (`test-docker-compose.yml`) instead of the main Docker Compose file, providing better isolation and avoiding conflicts with development environments.

## Architecture Changes

### Before ❌
- Tests used `docker-compose.yml` (main/production environment)
- Port conflicts with development environment (29092)
- No isolation between test and development
- Inconsistent usage across test files

### After ✅
- Tests use `tests/test-docker-compose.yml` (dedicated test environment)
- Isolated test ports (29093 for Kafka)
- Complete test stack including archive generator
- Consistent usage across all test files

## Docker Compose Files

### `docker-compose.yml` (Main/Production)
```yaml
services:
  broker:           # Port 29092
  kafka-ui:         # Port 8080
  archive-generator: # Main app
```
**Purpose**: Production, development, and full stack deployments

### `tests/test-docker-compose.yml` (Test Environment)
```yaml
services:
  test-broker:           # Port 29093
  test-archive-generator: # Test app with test config
  test-kafka-ui:         # Port 8090
```
**Purpose**: Isolated integration testing

## Test Fixtures

### `test_kafka_only` 
- **What**: Only test Kafka broker (lightweight)
- **Port**: 29093
- **Use for**: Fast Kafka functionality tests
- **Runtime**: ~10-15 seconds

### `test_full_stack`
- **What**: Complete test environment (Kafka + Archive Generator)
- **Port**: 29093 (Kafka), test app container
- **Use for**: End-to-end integration tests
- **Runtime**: ~30-60 seconds

### Legacy Fixtures (Still Available)
- `main_kafka_only`: Main Kafka on port 29092
- `full_stack`: Complete main stack
- **Use for**: Production-like testing when needed

## Test File Mapping

| Test File | Environment | Purpose | Fixtures |
|-----------|-------------|---------|----------|
| `test_fast.py` | Test | Quick smoke tests | `test_kafka_only` |
| `test_kafka_core.py` | Test | Kafka functionality | `test_kafka_only` |
| `test_archive_event_integration.py` | Test | Service integration | `test_kafka_only` |
| `test_docker_infrastructure.py` | Test | Container health | `test_kafka_only`, `test_full_stack` |
| `test_docker_compose.py` | Test | End-to-end | `test_full_stack` |
| `test_complete_integration.py` | None | Component tests | No Docker needed |

## Key Benefits

### 🚀 **Faster Development**
- Test environment starts faster (no app rebuild needed for simple tests)
- Parallel development and testing possible

### 🔒 **Better Isolation**
- No conflicts between development and test environments
- Test data separated from development data
- Different ports prevent accidental cross-contamination

### 🧹 **Cleaner Architecture**
- Clear separation of concerns
- Test-specific configuration
- Consistent patterns across all tests

### 🎯 **More Reliable**
- Tests don't interfere with running development services
- Predictable test environment state
- Better error isolation

## Usage Examples

### Quick Development Testing
```bash
# Only start test Kafka (fast)
pytest tests/integration/test_fast.py --run-integration -v
```

### Full Integration Testing
```bash
# Start complete test stack
pytest tests/integration/test_docker_compose.py --run-integration -v
```

### Kafka-Only Testing
```bash
# Test Kafka functionality without app
pytest tests/integration/kafka/ --run-integration -v
```

## Environment Variables

### Test Environment
- `ARCHIVE_ENV=testing`
- `KAFKA_BOOTSTRAP_SERVERS=test-broker:9092`
- `KAFKA_CONSUMER_GROUP=test_archive_generator_group`

### Configuration
- Test config file: `tests/integration/test_app_config.yaml`
- Test archives: `test_archives/` directory
- Test compose: `tests/test-docker-compose.yml`

## Migration Guide

### If you have existing tests using `docker-compose.yml`:

1. **Change imports**:
   ```python
   # Before
   from tests.fixtures.docker_fixtures import full_stack
   
   # After  
   from tests.fixtures.docker_fixtures import test_full_stack
   ```

2. **Update compose file references**:
   ```python
   # Before
   COMPOSE_FILE = "docker-compose.yml"
   
   # After
   TEST_COMPOSE_FILE = "tests/test-docker-compose.yml"
   ```

3. **Update container names**:
   ```python
   # Before: broker, archive-generator
   # After: test-broker, test-archive-generator
   ```

4. **Update ports**:
   ```python
   # Before: localhost:29092
   # After: localhost:29093
   ```

## Best Practices

1. **Use `test_kafka_only` for lightweight tests** that only need Kafka
2. **Use `test_full_stack` for end-to-end tests** that need the complete application
3. **Keep test data isolated** in `test_archives/` directory
4. **Use test-specific configuration** in `test_app_config.yaml`
5. **Clean up properly** (fixtures handle this automatically)

This architecture provides better separation between development and testing while maintaining full integration test capabilities.
