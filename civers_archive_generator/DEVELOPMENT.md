# 🛠️ Development Guide

Day-to-day development workflow and commands for the Archive Generator.

## Development Workflow

### Daily Setup
```bash
# Start development services
docker compose up -d broker kafka-ui

# Start the application in development mode
uv run python main_app.py
```

### Testing Workflow
```bash
# Quick unit tests (no Docker needed)
uv run pytest -k "not (kafka or integration or e2e)" -v

# Fast integration tests (~15 seconds)  
python3 -m pytest tests/integration/test_fast.py --run-integration -v

# Full integration tests (~60 seconds)
SKIP_BUILD=true python3 -m pytest tests/integration/ --run-integration -v

# All tests
uv run pytest -v
```

### Using the Test Runner
```bash
# Use the convenient test runner script
./run_tests.sh unit          # Unit tests only
./run_tests.sh integration   # Integration tests
./run_tests.sh all          # Everything
./run_tests.sh coverage     # With coverage report
```

## Development Commands

### Configuration Management
```bash
# Check current configuration
uv run python -c "
from config.loaders import YamlFileConfigLoader
config = YamlFileConfigLoader().load()
print(f'Environment: {config.app.name}')
print(f'Domains: {[d.name for d in config.domains]}')
"

# Test configuration loading
uv run python -c "from config.loaders import ConfigLoaderFactory; print('Config loads:', ConfigLoaderFactory.create().load().app.name)"
```

### Kafka Management
```bash
# Access Kafka UI (after starting services)
open http://localhost:8089

# Send test messages with default URLs
uv run python send_test_requests.py

# Archive specific URLs
uv run python send_test_requests.py https://example.com https://httpbin.org/get

# Use testing environment
uv run python send_test_requests.py --environment=testing https://example.com

# Enable debug logging
uv run python send_test_requests.py --verbose https://example.com

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
from config.loaders import YamlFileConfigLoader

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
```

## Code Structure

### Component Overview
```
├── main_app.py                 # Application entry point
├── config/                     # Configuration management
│   ├── models.py              # Pydantic models
│   ├── loaders.py             # Environment-based config loading
│   └── data/                  # YAML configuration files
├── transport_services/         # Event-driven messaging
│   └── kafka/                 # Kafka implementation
├── archive_services/           # Business logic
├── archive_generators/         # Strategy pattern for archiving
│   ├── scoop_archive_generator_strategy.py  # Scoop integration
│   └── archive_generator_factory.py         # Factory pattern
├── storage/                    # Storage abstraction
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
export ARCHIVE_ENV=development  # Use development config
export UV_LOG_LEVEL=debug      # Verbose logging
```

### Testing  
```bash
export ARCHIVE_ENV=testing     # Use testing config
export SKIP_BUILD=true         # Skip Docker builds in tests
```

### Docker
```bash
export ARCHIVE_ENV=docker      # Use Docker config
export KAFKA_BOOTSTRAP_SERVERS=broker:9092
```

## Debugging

### Common Debugging Commands
```bash
# Check component health
uv run python -c "
from archive_services import ArchiveService
from config.loaders import YamlFileConfigLoader
service = ArchiveService(YamlFileConfigLoader().load())
health = service.health_check()
print('Health:', health['healthy'])
print('Details:', health['details'])
"

# Test Scoop dependencies
uv run python -c "
from archive_generators.scoop_archive_generator_strategy import ScoopArchiveGeneratorStrategy
from config.loaders import YamlFileConfigLoader
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

## Performance Tips

- Use `test_kafka_only` fixture for fast integration tests
- Set `SKIP_BUILD=true` to avoid Docker rebuilds
- Use reusable Docker containers during development
- Run unit tests first, then integration tests

## VS Code Integration

If you're using VS Code, run the setup script:
```bash
./setup_vscode_testing.sh
```

This gives you:
- Test Explorer integration
- Pre-configured debug tasks  
- Quick testing commands in Command Palette
- Docker service management

## Contribution Guidelines

1. Run tests before committing: `./run_tests.sh all`
2. Follow existing code patterns and naming conventions
3. Add tests for new functionality
4. Update documentation for new features
5. Use descriptive commit messages

## Getting Help

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Look at existing tests for usage examples  
- Check logs in `archive_generator.log`
- Use Docker logs: `docker compose logs`