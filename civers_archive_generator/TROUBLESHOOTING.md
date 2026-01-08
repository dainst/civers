# 🔧 Troubleshooting Guide

Common issues and solutions for the Archive Generator.

## Quick Diagnostics

Run this command to check system health:

```bash
# Quick system check
uv run python -c "
print('=== Archive Generator Diagnostics ===')
try:
    # Test configuration
    from config.loaders import YamlFileConfigLoader
    config = YamlFileConfigLoader().load()
    print('✅ Configuration loads successfully')
    print(f'   Environment: {config.app.name}')
    print(f'   Domains configured: {len(config.domains)}')
    
    # Test dependencies
    import subprocess
    node_result = subprocess.run(['node', '--version'], capture_output=True, text=True)
    print(f'✅ Node.js: {node_result.stdout.strip()}')
    
    # Test Scoop
    from archive_generators.scoop_archive_generator_strategy import ScoopArchiveGeneratorStrategy
    strategy = ScoopArchiveGeneratorStrategy(config)
    print('✅ Scoop dependencies verified')
    
    # Test archive service
    from archive_services import ArchiveService
    service = ArchiveService(config)
    health = service.health_check()
    print(f'✅ Archive service healthy: {health[\"healthy\"]}')
    
except Exception as e:
    print(f'❌ Issue found: {e}')
    import traceback
    traceback.print_exc()
"
```

## Common Issues

### 1. Kafka Connection Issues

**Symptoms:**

- "Could not connect to Kafka broker"
- "Kafka broker not ready"
- Application hangs on startup

**Solutions:**

```bash
# Check if Kafka is running
docker compose ps

# Start Kafka if needed
docker compose up -d broker

# Check Kafka logs
docker compose logs broker -f

# Wait for Kafka to be ready
# Look for "started (kafka.server.KafkaServer)" in logs

# Test Kafka connectivity
docker compose exec broker kafka-topics.sh --bootstrap-server localhost:9092 --list

# Reset Kafka if corrupted
docker compose down -v
docker compose up -d broker
```

**Port conflicts:**

```bash
# Check what's using Kafka ports
lsof -i :29092
lsof -i :9092

# Kill conflicting processes if needed
sudo kill -9 <PID>
```

### 2. Node.js / Scoop Issues

**Symptoms:**

- "Node.js not found"
- "Scoop CLI not working properly"  
- "Scoop dependencies not available"

**Solutions:**

```bash
# Check Node.js installation
node --version  # Should be 20+
npm --version

# Install Node.js 20 if needed (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Scoop dependencies
cd lib/scoop
npm ci
cd ../..

# Test Scoop CLI directly
node lib/scoop/bin/cli.js --version

# Install Playwright browsers for Scoop
uv run playwright install chromium
```

### 3. Python Dependencies

**Symptoms:**

- Import errors
- "Module not found"
- uv command not found

**Solutions:**

```bash
# Install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Install project dependencies
uv sync

# Check Python version
python3 --version  # Should be 3.12+

# Alternative: use pip if uv unavailable
pip install -r requirements.txt
pip install playwright
playwright install chromium
```

### 4. Configuration Issues

**Symptoms:**

- "Configuration not found"
- "Environment detection failed"
- Invalid configuration errors

**Solutions:**

```bash
# Check configuration files exist
ls -la configs/data/defaults/
ls -la configs/data/environments/

# Test configuration loading
uv run python -c "
from config.loaders import YamlFileConfigLoader
config = YamlFileConfigLoader()
print('Environment detected:', config.environment)
data = config.load()
print('Config loaded:', data.app.name)
"

# Set explicit environment
export ARCHIVE_ENV=development
```

### 5. Archive Generation Failures

**Symptoms:**

- "Archive generation failed"
- Empty archive directories
- Timeout errors

**Solutions:**

```bash
# Check archive directory permissions
ls -la archives/
mkdir -p archives
chmod 755 archives

# Test URL accessibility
curl -I https://example.com

# Check Scoop CLI manually
node lib/scoop/bin/cli.js --version
node lib/scoop/bin/cli.js https://example.com -o /tmp/test.wacz

# Check available disk space
df -h .

# Increase timeout if needed (edit config)
# scoop_timeout_sec: 600  # 10 minutes
```

### 6. Test Failures

**Symptoms:**

- Tests hang or timeout
- Docker container issues
- Import errors in tests

**Solutions:**

```bash
# Clean Docker state
docker compose -f tests/test-docker-compose.yml down -v
docker compose down -v
docker system prune -f

# Run tests incrementally
./run_tests.sh unit           # Start with unit tests
./run_tests.sh integration    # Then integration tests

# Check test environment
export SKIP_BUILD=true  # Skip Docker builds
python3 -m pytest tests/integration/test_fast.py -v

# Fix permission issues
chmod +x run_tests.sh
```

### 7. Docker Issues

**Symptoms:**

- "Docker not found"
- Permission denied errors
- Container startup failures

**Solutions:**

```bash
# Check Docker installation
docker --version
docker compose --version

# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Start Docker service if needed
sudo systemctl start docker
sudo systemctl enable docker

# Clean Docker resources
docker system prune -a
docker volume prune
```

### 8. Performance Issues

**Symptoms:**

- Slow archive generation
- High memory usage
- Timeouts

**Solutions:**

```bash
# Monitor resource usage
htop
docker stats

# Increase available resources
# Edit config: scoop_timeout_sec: 600

# Check available disk space
df -h archives/

# Close unnecessary applications
# Ensure sufficient RAM (4GB+ recommended)
```

## Environment-Specific Issues

### Development Environment

```bash
# Common development fixes
export ARCHIVE_ENV=development
export UV_LOG_LEVEL=debug

# Restart services
docker compose restart broker
uv run python main.py
```

### Testing Environment

```bash
# Test environment fixes
export ARCHIVE_ENV=testing
export SKIP_BUILD=true

# Use isolated test containers
docker compose -f tests/test-docker-compose.yml up -d
```

### Docker Environment

```bash
# Docker-specific fixes
export ARCHIVE_ENV=docker
docker compose build --no-cache archive-generator
docker compose up -d
```

## Log Analysis

### Application Logs

```bash
# View real-time logs
tail -f archive_generator.log

# Search for errors
grep ERROR archive_generator.log
grep "❌" archive_generator.log

# View specific component logs
grep "Kafka" archive_generator.log
grep "Scoop" archive_generator.log
```

### Docker Logs

```bash
# All services
docker compose logs -f

# Specific services
docker compose logs broker -f
docker compose logs archive-generator -f

# Test environment
docker compose -f tests/test-docker-compose.yml logs -f
```

### Scoop Logs

After running archives, check individual operation logs:

```bash
# View Scoop execution logs
ls archives/*/scoop_*.log
cat archives/example_com/*/scoop_stdout.log
```

## Getting Help

### Self-Service Debugging

1. Run the diagnostics command above
2. Check relevant logs
3. Try the specific solutions for your symptoms
4. Check [DEVELOPMENT.md](DEVELOPMENT.md) for commands

### Before Reporting Issues

Include this information:

```bash
# System information
uv --version
python3 --version
node --version
docker --version

# Configuration info
echo $ARCHIVE_ENV
cat configs/data/environments/development.yaml

# Recent logs
tail -20 archive_generator.log
docker compose logs --tail=20
```

### Reset Everything

Nuclear option if everything is broken:

```bash
# Stop all services
docker compose -f tests/test-docker-compose.yml down -v
docker compose down -v

# Clean Docker
docker system prune -a -f

# Reset archives
rm -rf archives/

# Reinstall dependencies
rm -rf .venv uv.lock
uv sync
cd lib/scoop && rm -rf node_modules && npm ci && cd ../..

# Start fresh
docker compose up -d broker
uv run python main.py
```
