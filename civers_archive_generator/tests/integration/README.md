# Fast Integration Testing

## Problem Solved

The original integration test `test_can_publish_request_and_receive_events` was taking too long (3+ minutes) due to:

1. **Docker image rebuild**: Building the entire archive-generator image from scratch every time
2. **Long timeouts**: 120-180 second timeouts for Kafka consumers
3. **Complex setup**: Full Docker Compose stack with UI and archive processing

## Docker Container Requirements

### All integration tests require Docker containers to be running:

| Test File | Required Containers | Setup Command |
|-----------|-------------------|---------------|
| `test_fast.py` | `broker` | `docker compose up -d broker` |
| `test_kafka_core.py` | `broker` | `docker compose up -d broker` |
| `test_docker_infrastructure.py` | `broker`, `archive-generator` | `docker compose up -d` |
| `test_docker_compose.py` | `broker`, `kafka-ui`, `archive-generator` | `docker compose up -d` |

### Container Dependencies Summary:

**🐳 broker container (Kafka)**
- Required by: ALL integration tests
- Used for: Kafka topic operations, message publishing/consuming
- Commands that need it:
  - `docker exec broker bash -c "/opt/kafka/bin/kafka-topics.sh ..."`
  - `docker exec broker bash -c "/opt/kafka/bin/kafka-console-producer.sh ..."`
  - `docker exec broker bash -c "/opt/kafka/bin/kafka-console-consumer.sh ..."`

**🐳 archive-generator container**
- Required by: `test_docker_compose.py` (full tests)
- Used for: End-to-end archive processing
- Commands that need it:
  - `docker logs archive-generator`
  - Full workflow testing

**🐳 kafka-ui container**
- Required by: `test_docker_compose.py` (optional for debugging)
- Used for: Kafka monitoring via web UI

## Solution: Fast Test Suite

### 1. Ultra-Fast Tests (`test_fast.py`)
- **Runtime**: ~15 seconds for 7 tests
- **Requirements**: Only `broker` container
- **Purpose**: Quick smoke tests for development

```bash
# Start minimal setup
docker compose up -d broker

# Create topics quickly (auto-created by tests, but manual creation is faster)
docker exec broker bash -c "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic archive.requests --partitions 1"
docker exec broker bash -c "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic archive.status --partitions 1"

# Run fast tests
pytest tests/integration/test_fast.py --run-integration -v
```

### 2. Optimized Full Tests (`test_docker_compose.py`)
- **Runtime**: ~90 seconds (reduced from 3+ minutes)
- **Requirements**: `broker`, `kafka-ui`, `archive-generator` containers
- **Improvements**:
  - Skip rebuild with `SKIP_BUILD=true`
  - Reduced timeouts (30s status, 60s completion)
  - Use `example.com` instead of slow `arachne.dainst.org`
  - Better progress logging

```bash
# Skip rebuild for faster testing
SKIP_BUILD=true pytest tests/integration/test_docker_compose.py::test_can_publish_request_and_receive_events --run-integration -v

# Full test with minimal processing
pytest tests/integration/test_docker_compose.py::test_kafka_message_flow_with_processing --run-integration -v
```

### 2. Consolidated Kafka Tests (`test_kafka_core.py`)
- **Runtime**: ~30 seconds
- **Requirements**: Only `broker` container
- **Purpose**: All Kafka functionality testing (publishing, topics, connections)

### 3. Docker Infrastructure Tests (`test_docker_infrastructure.py`)
- **Runtime**: ~20 seconds
- **Requirements**: `broker` and `archive-generator` containers
- **Purpose**: Container health and service status testing

## Usage Recommendations

### During Development (Daily)
```bash
# Ultra-fast smoke test (15 seconds) - REQUIRES: broker container
docker compose up -d broker
pytest tests/integration/test_fast.py --run-integration -v
```

### Before Commit (Thorough)
```bash
# Kafka functionality test (30 seconds) - REQUIRES: broker container
docker compose up -d broker
pytest tests/integration/test_kafka_core.py --run-integration -v

# Docker infrastructure test (20 seconds) - REQUIRES: broker + archive-generator
docker compose up -d
pytest tests/integration/test_docker_infrastructure.py --run-integration -v

# Full integration test with optimizations (90 seconds) - REQUIRES: all containers
SKIP_BUILD=true pytest tests/integration/test_docker_compose.py --run-integration -v
```

### CI/CD Pipeline (Complete)
```bash
# Full test with fresh build (3 minutes) - REQUIRES: all containers
docker compose up -d
pytest tests/integration/test_docker_compose.py --run-integration -v
```

## Test Categories

| Test File | Runtime | Purpose | Docker Requirements |
|-----------|---------|---------|-------------------|
| `test_fast.py` | 15s | Development smoke tests | `broker` only |
| `test_kafka_core.py` | 30s | Kafka functionality | `broker` only |
| `test_docker_infrastructure.py` | 20s | Container/service health | `broker` + `archive-generator` |
| `test_docker_compose.py` | 90s+ | Full integration | `broker` + `kafka-ui` + `archive-generator` |

## Common Docker Issues

**❌ Container not found errors:**
```bash
# Error: docker exec broker bash -c "..."
# Solution: Start the broker container
docker compose up -d broker
```

**❌ Tests skip with "Required containers not running":**
```bash
# Solution: Check container status and start if needed
docker ps | grep broker
docker compose up -d broker
```

**❌ Long test times:**
```bash
# Solution: Use SKIP_BUILD to avoid rebuilding archive-generator
SKIP_BUILD=true pytest tests/integration/test_docker_compose.py --run-integration -v
```

## Environment Variables

- `SKIP_BUILD=true`: Skip Docker image rebuild
- `--run-integration`: Enable integration tests  
- `-v`: Verbose output for debugging

This approach gives developers fast feedback while maintaining comprehensive testing for CI/CD.
