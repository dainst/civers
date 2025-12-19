# Docker Deployment Guide

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Archives directory with snapshot data

### Production Deployment

```bash
# Clone and navigate to project
git clone git@github.com:dainst/civers_archive_web_interface.git    
cd civers_archive_web_interface

# Start production container
docker compose up -d

# Verify deployment
curl http://localhost:8000/health
```

Application available at: http://localhost:8000

### Development Deployment

```bash
# Start development with hot reload
docker compose --profile development up civers-web-dev

# Access development server
curl http://localhost:8001/health
```

Development server available at: http://localhost:8001

## Configuration

### Environment Variables

| Variable | Production | Development | Description |
|----------|------------|-------------|-------------|
| `DEBUG` | `false` | `true` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | `DEBUG` | Logging verbosity |
| `PORT` | `8000` | `8000` | Internal container port |
| `STORAGE_PATH` | `/app/archives` | `/app/archives` | Archive data location |

### Volume Mounts

```yaml
volumes:
  - ./archives:/app/archives:ro  # Required: Archive data
  - ./logs:/app/logs             # Optional: Log persistence
```

## File Permissions

```bash
# Set permissions for archives and logs
sudo chown -R 1000:1000 ./archives ./logs
chmod -R 755 ./archives
```

## Health Monitoring

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f civers-web

# Health check
curl http://localhost:8000/health
```

Expected health response:
```json
{"status": "healthy", "service": "civers-archive-web-interface", "version": "1.0.0"}
```

