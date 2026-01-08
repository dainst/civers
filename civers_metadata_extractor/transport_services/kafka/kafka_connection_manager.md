# KafkaConnectionManager Documentation

## Purpose

The `KafkaConnectionManager` class provides centralized management of Kafka producer and consumer connections with robust error handling, configuration validation, and health monitoring. It extracts connection management concerns from the main transport service to improve maintainability and testability.

## Key Features

- **Lazy Initialization**: Connections are created only when explicitly requested
- **Health Monitoring**: Comprehensive health checks for both producer and consumer
- **Configuration Validation**: Validates Kafka settings before attempting connections
- **Robust Error Handling**: Graceful handling of connection failures with detailed logging
- **Resource Management**: Proper cleanup of connections and resources

## Supported Kafka Configuration

The `KafkaConnectionManager` works with the `KafkaConfig` model defined in `configs/models.py` and uses the configuration structure from `app_config.yaml`:

### Configuration Structure

```yaml
app:
  transport:
    kafka:
      bootstrap_servers: "localhost:29092"
      topics:
        # Required metadata extraction topics
        metadata_extraction_requests: "metadata.extraction.requests"
        metadata_extraction_started: "metadata.extraction.started"
        metadata_extracted: "metadata.extracted"
        metadata_extraction_failed: "metadata.extraction.failed"
        metadata_validation_completed: "metadata.validation.completed"
        metadata_status: "metadata.status"
        # Additional topics for enhanced functionality
        metadata_extraction_completed: "metadata.extraction.completed"
        metadata_quality: "metadata.quality"
      consumer_group: "metadata_extraction_group"
      health_check_enabled: true
      monitoring_enabled: true
```

### Required vs Optional Topics

**Topics Configuration**:

- `metadata_extraction_requests` - Incoming extraction requests
- `metadata_extraction_started` - Extraction process initiation events
- `metadata_extracted` - Successfully extracted metadata
- `metadata_extraction_failed` - Extraction failure events
- `metadata_validation_completed` - Validation completion events
- `metadata_status` - General status updates

**Optional Topics** (additional functionality):

- `metadata_extraction_completed` - Complete extraction workflow events
- `metadata_quality` - Quality metrics and analytics

### Configuration Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `bootstrap_servers` | `str` | ✅ | Kafka broker connection string | `"localhost:29092"` |
| `topics` | `Dict[str, str]` | ✅ | Topic name mappings (key=logical, value=physical) | See structure above |
| `consumer_group` | `str` | ✅ | Consumer group identifier for coordination | `"metadata_extraction_group"` |
| `health_check_enabled` | `bool` | ❌ | Enable health monitoring (default: true) | `true` |
| `monitoring_enabled` | `bool` | ❌ | Enable metrics collection (default: true) | `true` |

## Key Methods

### `__init__(kafka_config: KafkaConfig)`

- **Purpose**: Initialize the connection manager with Kafka configuration
- **Parameters**:
  - `kafka_config`: KafkaConfig object containing bootstrap servers, topics, consumer group
- **Returns**: None
- **Usage**:

  ```python
  connection_manager = KafkaConnectionManager(kafka_config)
  ```

### `setup_producer() -> KafkaProducer`

- **Purpose**: Initialize and configure Kafka producer with optimal settings
- **Parameters**: None
- **Returns**: KafkaProducer instance ready for publishing messages
- **Raises**: `KafkaError` if producer initialization fails
- **Configuration**:
  - JSON serialization for values and keys
  - Acknowledgment level: 1 (leader acknowledgment)
  - Retries: 3 attempts
  - Ordering guarantee: max 1 in-flight request
- **Usage**:

  ```python
  producer = await connection_manager.setup_producer()
  ```

### `setup_consumer(topics: List[str]) -> KafkaConsumer`

- **Purpose**: Initialize Kafka consumer for specified topics with consumer group coordination
- **Parameters**:
  - `topics`: List of topic names to consume from (required, non-empty)
- **Returns**: KafkaConsumer instance ready for message consumption
- **Raises**:
  - `ValueError` if no topics provided
  - `KafkaError` if consumer initialization fails
- **Configuration**:
  - JSON deserialization for values and keys
  - Consumer group management
  - Auto-offset reset: earliest (for testing scenarios)
  - Consumer timeout: 1 second for polling
- **Usage**:

  ```python
  consumer = await connection_manager.setup_consumer(['topic1', 'topic2'])
  ```

### `health_check() -> Dict[str, Any]`

- **Purpose**: Perform comprehensive health assessment of active Kafka connections
- **Parameters**: None
- **Returns**: Dictionary containing detailed health information:

  ```python
  {
      'healthy': bool,  # Overall health status
      'producer_healthy': bool,  # Producer connection status
      'consumer_healthy': bool,  # Consumer connection status
      'producer_exists': bool,  # Whether producer is initialized
      'consumer_exists': bool,  # Whether consumer is initialized
      'bootstrap_servers': str,  # Configured servers
      'consumer_group': str,  # Consumer group ID
      'topics_configured': int,  # Number of configured topics
      'last_check_time': str,  # ISO timestamp
      'connection_details': dict  # Configuration details for active connections
  }
  ```

- **Health Check Logic**:
  - Producer: Tests cluster metadata availability
  - Consumer: Verifies partition assignment capability
  - Overall: Healthy if all existing connections are healthy
- **Usage**:

  ```python
  health_status = await connection_manager.health_check()
  if health_status['healthy']:
      print("All connections healthy")
  ```

### `get_connection_status() -> Dict[str, Any]`

- **Purpose**: Get current connection status without performing new health checks
- **Parameters**: None
- **Returns**: Current connection status information (cached from last health check)
- **Usage**:

  ```python
  status = connection_manager.get_connection_status()
  ```

### `validate_configuration() -> Dict[str, Any]`

- **Purpose**: Validate Kafka configuration settings before attempting connections
- **Parameters**: None
- **Returns**: Dictionary containing validation results:

  ```python
  {
      'valid': bool,  # Whether configuration is valid
      'errors': List[str],  # Critical validation errors
      'warnings': List[str],  # Non-critical warnings
      'topics_count': int  # Number of configured topics
  }
  ```

- **Validation Checks**:
  - **Bootstrap servers**: Must be configured as non-empty string
  - **Consumer group**: Must be configured as non-empty string
  - **Topics structure**: Must be a dictionary (Dict[str, str])
  - **Topics presence**: Validates that at least one topic is configured
- **Usage**:

  ```python
  validation = connection_manager.validate_configuration()
  if not validation['valid']:
      print(f"Configuration errors: {validation['errors']}")
  ```

### `cleanup() -> None`

- **Purpose**: Clean up all Kafka connections and reset internal state
- **Parameters**: None
- **Returns**: None
- **Behavior**:
  - Safely closes producer and consumer connections
  - Handles cleanup errors gracefully with logging
  - Resets connection status tracking
  - Sets producer/consumer references to None
- **Usage**:

  ```python
  await connection_manager.cleanup()
  ```

## Function Signature Changes

### New Component - No Legacy Methods

This is a new component extracted from `KafkaTransportService`. The following methods were moved and redesigned:

#### Extracted Methods

- **Original**: `KafkaTransportService._setup_producer()`
- **New**: `KafkaConnectionManager.setup_producer()`
- **Changes**:
  - Now async (for consistency with other methods)
  - Returns the producer instance
  - Enhanced error handling with KafkaError

- **Original**: `KafkaTransportService._setup_consumer()`
- **New**: `KafkaConnectionManager.setup_consumer(topics: List[str])`
- **Changes**:
  - Now async (for consistency)
  - Requires explicit topics parameter
  - Returns the consumer instance
  - Better validation and error messages

- **Original**: Part of `KafkaTransportService.health_check()`
- **New**: `KafkaConnectionManager.health_check()`
- **Changes**:
  - Focused only on connection health
  - More detailed health information
  - Separated from workflow-specific health data

#### Call Sites Updated

The following files will need updates when `KafkaTransportService` is refactored:

1. **`transport_services/kafka/kafka_transport_service.py`**:
   - Remove `_setup_producer()` and `_setup_consumer()` methods
   - Update constructor to create `KafkaConnectionManager` instance
   - Update `start()` method to use connection manager
   - Update `health_check()` to use connection manager health data
   - Update `stop()/cleanup()` to use connection manager cleanup

2. **`main.py`**:
   - No direct changes needed (uses transport service interface)

3. **`scripts/civers_health_check.py`**:
   - No direct changes needed (uses transport service interface)

## Integration Points

### With KafkaTransportService

```python
class KafkaTransportService:
    def __init__(self, config, metadata_service):
        # ... existing setup ...
        self.connection_manager = KafkaConnectionManager(self.kafka_config)
    
    async def start(self):
        # Setup connections through manager
        await self.connection_manager.setup_producer()
        topics = list(self.event_handlers.keys())
        if topics:
            await self.connection_manager.setup_consumer(topics)
```

### With Other Components

- **Event Publishing**: Uses producer from connection manager
- **Message Consumption**: Uses consumer from connection manager
- **Health Monitoring**: Integrates connection health with service health
- **Configuration**: Validates Kafka settings before service startup

## Usage Examples

### Basic Setup

```python
from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager
from configs.yaml_file_loader_config import YamlFileConfigLoader

# Load configuration
config = YamlFileConfigLoader("app_config.yaml").load()
kafka_config = config.app.transport.kafka

# Create connection manager
connection_manager = KafkaConnectionManager(kafka_config)

# Validate configuration first
validation = connection_manager.validate_configuration()
if not validation['valid']:
    raise ValueError(f"Invalid Kafka config: {validation['errors']}")

# Setup connections
producer = await connection_manager.setup_producer()
consumer = await connection_manager.setup_consumer(['requests', 'responses'])

# Check health
health = await connection_manager.health_check()
print(f"Connections healthy: {health['healthy']}")

# Cleanup when done
await connection_manager.cleanup()
```

### Error Handling

```python
try:
    producer = await connection_manager.setup_producer()
    print("Producer ready for publishing")
except KafkaError as e:
    print(f"Producer setup failed: {e}")
    # Handle producer failure - maybe continue with consumer only

try:
    consumer = await connection_manager.setup_consumer(['topic1'])
    print("Consumer ready for messages")
except ValueError as e:
    print(f"Invalid topics provided: {e}")
except KafkaError as e:
    print(f"Consumer setup failed: {e}")
```

### Health Monitoring

```python
async def monitor_connections():
    while True:
        health = await connection_manager.health_check()
        
        if not health['healthy']:
            print("Connection issues detected:")
            if not health['producer_healthy']:
                print("  - Producer connection failed")
            if not health['consumer_healthy']:
                print("  - Consumer connection failed")
        
        await asyncio.sleep(30)  # Check every 30 seconds
```

## Important Notes

### Configuration Validation Behavior

✅ **Updated Implementation**: The `validate_configuration()` method now only validates that at least one topic is configured, providing more flexible topic configuration while maintaining basic validation.

The validation works because:

1. **Model-level validation** in `KafkaConfig.validate_metadata_topics()` runs first during config loading
2. **Connection manager validation** provides additional runtime checks
3. Topics can be configured flexibly based on application needs

### Topic Mapping Logic

The configuration uses **logical → physical** topic name mapping:

- **Logical names**: Used in code (e.g., `metadata_extraction_requests`)  
- **Physical names**: Used in Kafka broker (e.g., `"metadata.extraction.requests"`)

This allows changing Kafka topic names without code changes.

## Design Decisions

### Why Optional Connections?

- **Flexibility**: Services may only need producer OR consumer, not both
- **Lazy Initialization**: Connections created only when explicitly requested
- **Error Resilience**: If producer setup fails, consumer can still work
- **Resource Efficiency**: No unnecessary connections created

### Why Async Methods?

- **Consistency**: Matches async pattern used throughout transport services
- **Future-Proofing**: Allows for async configuration loading or connection pooling
- **Integration**: Seamless integration with async service lifecycle methods

### Why Separate Health Check?

- **Focused Responsibility**: Connection health separate from business logic health
- **Detailed Monitoring**: Granular connection status information
- **Reusability**: Health data usable by multiple monitoring systems

## Testing Considerations

### Unit Test Coverage

- Configuration validation with various invalid configs
- Producer setup with mocked Kafka dependencies
- Consumer setup with different topic combinations
- Health checks with various connection states
- Cleanup with different connection states
- Error handling for all connection failures

### Integration Test Requirements

- Real Kafka cluster connection testing
- Producer/consumer message flow validation
- Health check accuracy with actual connections
- Configuration validation with real Kafka clusters
