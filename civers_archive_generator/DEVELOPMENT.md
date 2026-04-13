# 🛠️ Development Guide

Day-to-day development workflow and commands for the Archive Generator.

## Development Workflow

### Daily Setup

```bash
# Start development services
docker compose up -d broker kafka-ui

# Start the application in development mode
uv run python main.py
```

### Testing Workflow

```bash
# Run all unit tests with verbose output
uv run pytest tests/unit/ -v

# Run tests with coverage reporting
uv run pytest --cov=.

# Run a specific unit test file
uv run pytest tests/unit/configs/test_storage_config.py -v
```


### Test Runner Shortcuts

```bash
# Run tests and open HTML coverage report
uv run pytest --cov=. --cov-report=html
```

## Development Commands

### Configuration Management

```bash
# Check current configuration
uv run python -c "
from configs.loaders import YamlFileConfigLoader
config = YamlFileConfigLoader().load()
print(f'Environment: {config.app.name}')
print(f'Domains: {[d.name for d in config.domains]}')
"

# Test configuration loading
uv run python -c "from configs.loaders import YamlFileConfigLoader; print('Config loads:', YamlFileConfigLoader().load().app.name)"
```

### Kafka Management

```bash
# Access Kafka UI (after starting services)
open http://localhost:8089

# Send test messages with default URLs
uv run python scripts/send_test_requests.py

# Archive specific URLs
uv run python scripts/send_test_requests.py https://example.com https://httpbin.org/get

# Use testing environment
uv run python scripts/send_test_requests.py --environment=testing https://example.com

# Enable debug logging
uv run python scripts/send_test_requests.py --verbose https://example.com

# Monitor Kafka logs
docker compose logs broker -f

# List Kafka topics
docker compose exec broker kafka-topics.sh --bootstrap-server localhost:9092 --list

# Reset Kafka data (when things get messy)
docker compose down -v
docker compose up -d broker
```

### Archive Testing

```bash
# Test specific URLs
uv run python -c "
import asyncio
from archive_services import ArchiveService
from configs.loaders import YamlFileConfigLoader

async def test_url():
    config = YamlFileConfigLoader().load()
    service = ArchiveService(config)
    result = await service.create_archive('https://example.com', 'test-123')
    print('Archive result:', result['success'])
    return result

result = asyncio.run(test_url())
"

# Check archive output
ls -la archives/*/

> [!NOTE]
> Testing the CIVERS REST API backend via `demo_storage.py` requires a running CIVERS API instance (typically on port 8000).
```

## Code Structure

### Component Overview

```text
├── main.py                 # Application entry point
├── configs/                    # Configuration management
│   ├── models.py              # Pydantic models
│   ├── loaders.py             # Environment-based config loading
│   └── data/                  # YAML configuration files
├── transport_services/         # Event-driven messaging
│   └── kafka/                 # Kafka implementation
├── archive_services/           # Business logic
├── archive_generators/         # Strategy pattern for archiving
│   ├── scoop_archive_generator_strategy.py  # Scoop integration
│   └── archive_generator_factory.py         # Factory pattern
├── storage_layer/              # Storage abstraction
└── tests/                     # Comprehensive test suite
```

### Adding New Features

#### Add a New Archive Generator

1. Create class implementing `ArchiveGeneratorStrategyInterface`
2. Register in `ArchiveGeneratorFactory`
3. Add configuration support in domain config
4. Write tests

#### Add a New Transport

1. Create class implementing `TransportServiceInterface`
2. Add configuration model
3. Update main app to use new transport
4. Write integration tests

#### Add New Domain Configuration

```yaml
# In configs/data/defaults/domains.yaml or environment-specific files
domains:
  - name: newdomain.com
    artifacts: [warc, html, screenshots]  
    webpage_types: dynamic
```

## Environment Variables

### Development

```bash
export CONFIG_ENVIRONMENT=development  # Use development config
export UV_LOG_LEVEL=debug              # Verbose logging
```

### Testing  

```bash
export CONFIG_ENVIRONMENT=testing     # Use testing config
export SKIP_BUILD=true                # Skip Docker builds in tests
```

### Docker

```bash
export CONFIG_ENVIRONMENT=docker      # Use Docker config
export KAFKA_BOOTSTRAP_SERVERS=broker:9092
```

## Debugging

### Common Debugging Commands

```bash
# Check component health
uv run python -c "
from archive_services import ArchiveService
from configs.loaders import YamlFileConfigLoader
service = ArchiveService(YamlFileConfigLoader().load())
health = service.health_check()
print('Health:', health['healthy'])
print('Details:', health['details'])
"

# Test Scoop dependencies
uv run python -c "
from archive_generators.scoop_archive_generator_strategy import ScoopArchiveGeneratorStrategy
from configs.loaders import YamlFileConfigLoader
try:
    strategy = ScoopArchiveGeneratorStrategy(YamlFileConfigLoader().load())
    print('✅ Scoop dependencies OK')
except Exception as e:
    print('❌ Scoop issue:', e)
"

# Check Node.js and Scoop CLI
node lib/scoop/bin/cli.js --version
```

### Log Files

```bash
# Application logs
tail -f archive_generator.log

# Individual archive logs (after creating archives)
ls archives/*/scoop_*.log
```
## Getting Help

- Look at existing tests for usage examples  
- Check logs in `archive_generator.log`
- Use Docker logs: `docker compose logs`
