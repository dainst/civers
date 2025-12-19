# Utility Scripts

Development and operational scripts for managing Kafka infrastructure, testing connectivity, and maintaining the CIVERS Metadata Extractor system.

## Overview

The scripts directory contains essential utilities for:

- **Kafka Management**: Setup, cleanup, and topic management
- **Connection Testing**: Validate Kafka connectivity and health
- **Development Workflow**: Streamlined development environment setup
- **Operational Support**: Production deployment and maintenance tasks

## Script Inventory

### Infrastructure Management Scripts

| Script | Purpose | Usage | Prerequisites |
|--------|---------|-------|---------------|
| `setup_kafka.sh` | Complete Kafka infrastructure setup | `./scripts/setup_kafka.sh` | Docker, Docker Compose |
| `cleanup_kafka.sh` | Clean shutdown and reset | `./scripts/cleanup_kafka.sh` | Running Docker services |
| `create_topics.py` | Create required Kafka topics | `python3 scripts/create_topics.py` | Python 3.12+, kafka-python |
| `civers_health_check.py` | CIVERS system health check and validation | `uv run civers-health-check` | Python 3.12+, all dependencies |
| `kafka_monitor.py` | Monitor Kafka messages and events | `uv run kafka-monitor` | Python 3.12+, running Kafka |

## Detailed Script Documentation

### setup_kafka.sh

**Purpose**: Complete Kafka infrastructure initialization and setup

**Location**: `scripts/setup_kafka.sh`

**Features**:
- Docker service validation and startup
- Kafka and Zookeeper container orchestration
- Automatic topic creation via Python integration
- Connectivity testing and validation
- Comprehensive error handling and logging

**Usage**:
```bash
# Make script executable (if needed)
chmod +x scripts/setup_kafka.sh

# Run complete setup
./scripts/setup_kafka.sh
```

**Execution Flow**:
1. **Environment Validation**: Check Docker availability and status
2. **Service Startup**: Launch Kafka and Zookeeper via Docker Compose
3. **Service Readiness**: Wait for containers to be fully operational
4. **Topic Creation**: Execute `create_topics.py` to initialize required topics
5. **Connectivity Test**: Run `test_kafka_connection.py` to verify setup
6. **Status Report**: Display service status and management commands

**Output Example**:
```
🚀 Starting Kafka infrastructure setup...
✅ Docker is running and available
📦 Starting Kafka infrastructure...
⏳ Waiting for services to be ready...
📋 Creating required topics...
🔍 Testing connectivity...
🎉 Kafka infrastructure setup completed!
📋 Services available:
   Kafka Broker: localhost:29092
   Kafka UI: http://localhost:8088
```

**Error Handling**:
- Docker availability validation
- Service startup failure detection
- Topic creation error recovery
- Connectivity test failure reporting

### cleanup_kafka.sh

**Purpose**: Clean shutdown and environment reset

**Location**: `scripts/cleanup_kafka.sh`

**Features**:
- Graceful container shutdown
- Volume and network cleanup
- Data persistence removal (optional)
- Complete environment reset

**Usage**:
```bash
# Clean shutdown with data preservation
./scripts/cleanup_kafka.sh

# Complete reset including data
./scripts/cleanup_kafka.sh --purge-data
```

**Execution Flow**:
1. **Container Shutdown**: Stop all Kafka-related containers
2. **Resource Cleanup**: Remove networks and temporary volumes
3. **Data Management**: Optional data directory cleanup
4. **Verification**: Confirm clean environment state

### create_topics.py

**Purpose**: Automated Kafka topic creation from configuration

**Location**: `scripts/create_topics.py:10-83`

**Features**:
- Configuration-driven topic creation
- Automatic topic discovery from `app_config.yaml`
- Batch topic creation with error handling
- Topic verification and listing

**Configuration Integration**:
```python
def load_topics_from_config(config_path="app_config.yaml"):
    """Load topic configuration from YAML file."""
    
    topics = config.get('app', {}).get('transport', {}).get('kafka', {}).get('topics', {})
    return topics
```

**Topic Creation Process**:
```python
# Create topic objects with standard configuration
topic_obj = NewTopic(
    name=topic_name,
    num_partitions=3,      # Standard partitioning
    replication_factor=1   # Single node development
)
```

**Usage**:
```bash
# Create topics from default configuration
python3 scripts/create_topics.py

# With UV (recommended)
uv run python3 scripts/create_topics.py
```

**Created Topics** (from `app_config.yaml`):
- `metadata.extraction.requests` - Input requests
- `metadata.extraction.started` - Processing notifications  
- `metadata.extracted` - Successful extractions
- `metadata.extraction.failed` - Error notifications
- `metadata.validation.completed` - Validation results
- `metadata.status` - Status updates
- `metadata.extraction.completed` - Completion events
- `metadata.quality` - Quality metrics

**Error Handling**:
- Configuration file validation
- Kafka connectivity verification
- Topic creation error recovery
- Existing topic handling (graceful)


### civers_health_check.py

**Purpose**: Comprehensive CIVERS system health check and validation

**Location**: `scripts/civers_health_check.py`

**Features**:
- Validates all required dependencies
- Checks Docker Kafka container status
- Tests Kafka transport service creation
- Verifies storage directory access
- Comprehensive configuration validation

**Health Check Components**:
1. **Dependency Check**: Validates Python packages (kafka, pydantic, yaml, asyncio)
2. **Docker Check**: Confirms Kafka broker container is running
3. **Configuration Check**: Loads and validates app_config.yaml
4. **Low-level Connectivity Tests**:
   - **Kafka Admin Client**: Tests broker connectivity and topic listing
   - **Kafka Producer**: Tests message publishing with real messages
   - **Kafka Consumer**: Tests message consumption capabilities
5. **High-level Integration Tests**:
   - **Application Producer**: Tests KafkaTransportService producer creation
   - **Application Consumer**: Tests KafkaTransportService consumer creation
6. **Storage Check**: Verifies archive directory accessibility

**Usage**:
```bash
# Standard health check
uv run civers-health-check

# Debug mode (uses test configuration)
UV_LOG_LEVEL=debug uv run civers-health-check
```

**Output Example**:
```
🏥 CIVERS System Health Check
==================================================
✅ All required dependencies are available
✅ Kafka Docker container is running
✅ Configuration loaded successfully
   - Domains configured: 3
   - Kafka topics: 8
🔍 Testing low-level Kafka connectivity...
✅ Kafka admin client connectivity verified
   - Available topics: 8
✅ Kafka producer connectivity verified
   - Test message sent to metadata.status at offset 42
✅ Kafka consumer connectivity verified
   - Consumer ready (no messages to consume)
🚀 Testing application-level Kafka integration...
✅ Kafka transport service can be created (producer included)
✅ Kafka transport service consumer can be created
✅ Storage directory is accessible: archives
==================================================
🏥 Health Check Results: 9/9 passed
🎉 All health checks passed! System is ready.
```

### kafka_monitor.py

**Purpose**: Real-time monitoring of Kafka messages and metadata extraction events

**Location**: `scripts/kafka_monitor.py`

**Features**:
- Real-time event monitoring across multiple topics
- Status update tracking and statistics
- Completion and failure event processing
- Quality assessment monitoring
- Processing time metrics and success rates

**Monitored Topics**:
- `metadata.status` - Status updates during processing
- `metadata.extracted` - Successful extraction completions
- `metadata.extraction.failed` - Processing failures
- `metadata.quality` - Quality assessment results

**Event Processing**:
```python
# Status events: Track request progress
await self.handle_status_event(value, key, partition, offset)

# Completion events: Success metrics and processing times
await self.handle_completed_event(value, key, partition, offset)

# Failure events: Error tracking and diagnostics
await self.handle_failed_event(value, key, partition, offset)

# Quality events: Metadata quality assessments
await self.handle_quality_event(value, key, partition, offset)
```

**Usage**:
```bash
# Start monitoring (runs until Ctrl+C)
uv run kafka-monitor

# Debug mode monitoring
UV_LOG_LEVEL=debug uv run kafka-monitor
```

**Monitoring Output**:
```
📊 Metadata Extraction Status Monitor
📊 Monitoring for Kafka messages (Press Ctrl+C to stop)...
✅ Metadata Extraction Completed - req-123
   URL: https://arachne.dainst.org/entity/123
   Domain: arachne.dainst.org
   Mappers: ['jsonld']
   Processing time: 2.35s
📈 Stats: Active=0, Completed=1, Failed=0, Total=1, Quality=0, Avg Time=2.35s
```

**Statistics Tracking**:
- Active requests in progress
- Completed extractions with success metrics
- Failed extractions with error categorization
- Quality assessments performed
- Average processing times

## Development Workflow Integration

### Development Environment Setup

```bash
# Complete development environment setup
./scripts/setup_kafka.sh

# Start metadata extractor
uv run python3 main.py

# In another terminal: run tests
uv run pytest
```

### Testing Workflow

```bash
# Reset environment for testing
./scripts/cleanup_kafka.sh
./scripts/setup_kafka.sh

# Run integration tests
uv run pytest -m integration

# Monitor Kafka during tests
uv run civers-health-check
```

### Debugging Workflow

```bash
# Clean setup for debugging
./scripts/cleanup_kafka.sh
./scripts/setup_kafka.sh

# Test connectivity in isolation
uv run civers-health-check

# Monitor topic activity
./scripts/monitor_topics.sh  # If available
```

## Operational Usage

### Production Deployment

```bash
# Production-ready setup (with data persistence)
KAFKA_PERSIST_DATA=true ./scripts/setup_kafka.sh

# Verify production configuration
uv run civers-health-check
```

### Monitoring and Maintenance

```bash
# Regular health check
uv run civers-health-check

# Topic management
python3 scripts/create_topics.py --list-existing

# Performance monitoring
uv run civers-health-check
```

### Troubleshooting

```bash
# Diagnostic information
./scripts/setup_kafka.sh --diagnose

# Clean reset for issues
./scripts/cleanup_kafka.sh --purge-data
./scripts/setup_kafka.sh
```

## Error Scenarios and Recovery

### Common Issues and Solutions

#### Docker Not Running
```bash
# Error: Docker is not running
# Solution: Start Docker Desktop or Docker daemon
sudo systemctl start docker  # Linux
# or start Docker Desktop application
```

#### Port Conflicts
```bash
# Error: Port 29092 already in use
# Solution: Check for conflicting services
lsof -i :29092
docker-compose down  # Stop conflicting containers
```

#### Topic Creation Failures
```bash
# Error: Failed to create topics
# Solution: Verify Kafka is ready and retry
docker-compose logs kafka
sleep 10
python3 scripts/create_topics.py
```

#### Connectivity Issues
```bash
# Error: Connection refused
# Solution: Check Kafka service status
docker-compose ps
docker-compose restart kafka
uv run civers-health-check
```

### Recovery Procedures

#### Complete Environment Reset
```bash
# Nuclear option: complete reset
docker-compose down -v  # Remove volumes
docker system prune -f  # Clean unused resources
./scripts/setup_kafka.sh
```

#### Service-Specific Recovery
```bash
# Kafka service issues
docker-compose restart kafka
sleep 15
uv run civers-health-check


## Integration with Main Application

### Application Startup Dependencies

```python
# In main.py:66-85
async def initialize(self):
    """Initialize application with Kafka health check."""
    
    # Verify Kafka transport service
    health = await self.kafka_transport.health_check()
    if not health['healthy']:
        logger.error("❌ Kafka transport service health check failed")
        # Could trigger scripts/setup_kafka.sh automatically
```

### Health Check Integration

```python
# Integration with transport services health checking
from scripts.civers_health_check import SystemHealthCheck

def integrated_health_check():
    """Integrate script-based health checks with application."""
    
    health_check = SystemHealthCheck()
    script_result = health_check.run_health_check()
    transport_result = kafka_transport.health_check()
    
    return {
        "script_health": script_result,
        "transport_health": transport_result,
        "overall_healthy": script_result and transport_result["healthy"]
    }
```

## Script Configuration

### Environment Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Override Kafka connection | `localhost:29092` | `kafka1:9092,kafka2:9092` |
| `KAFKA_PERSIST_DATA` | Enable data persistence | `false` | `true` |
| `SCRIPT_LOG_LEVEL` | Script logging verbosity | `INFO` | `DEBUG` |
| `TOPIC_REPLICATION_FACTOR` | Topic replication | `1` | `3` |

### Configuration File Integration

Scripts automatically read from `app_config.yaml`:

```yaml
app:
  transport:
    kafka:
      bootstrap_servers: "localhost:29092"
      topics:
        # Topics automatically created by create_topics.py
        metadata_extraction_requests: "metadata.extraction.requests"
        # ... additional topics
```

## Best Practices

### Development Usage

1. **Always run `setup_kafka.sh` before development**
2. **Use `uv run civers-health-check` to verify connectivity**
3. **Run `cleanup_kafka.sh` when switching branches**
4. **Monitor Docker resource usage during extended sessions**

### Production Usage

1. **Enable data persistence with environment variables**
2. **Increase replication factors for production topics**
3. **Monitor script execution logs for operational issues**
4. **Schedule regular health checks via `uv run civers-health-check`**

### Troubleshooting

1. **Always check Docker status first**
2. **Use verbose flags for detailed diagnostics**
3. **Verify network connectivity before Kafka operations**
4. **Keep configuration files in sync with script expectations**

## Implementation References

- **Setup Script**: `scripts/setup_kafka.sh:25-81`
- **Topic Creation**: `scripts/create_topics.py:22-83`
- **Health Check Script**: `scripts/civers_health_check.py:15-327`
- **Cleanup Process**: `scripts/cleanup_kafka.sh:10-50`
- **Docker Configuration**: `docker-compose.yml:15-45`
- **Application Integration**: `main.py:66-85`

---

**Purpose**: Development & Operations support | **Integration**: Docker + Python | **Usage**: Automated infrastructure management | **Health**: Comprehensive connectivity testing