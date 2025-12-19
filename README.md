# CIVERS - Coordinated Infrastructure for Versioned and Extensible Repository Systems

A comprehensive system for archiving web pages, extracting metadata, and managing digital artifacts. CIVERS integrates web archiving (WACZ), metadata extraction, and storage into a unified workflow.

## Components

| Component | Description |
|-----------|-------------|
| **Orchestrator** | Coordinates workflow and manages requests |
| **Archive Generator** | Creates WACZ archives, screenshots, and HTML snapshots |
| **Metadata Extractor** | Extracts structured metadata from archived pages |
| **Web Interface** | Provides storage and access to archived artifacts |

## Quick Start

### Prerequisites

- Docker 24.0+ with Docker Compose 2.0+
- Python 3.10+ with [uv](https://astral.sh/uv) package manager

### 1. Start Services

```bash
# Clone and navigate to the project
git clone <repository-url>
cd civers

# Start all services (first run takes a few minutes)
docker compose up -d

# Verify all services are healthy
docker compose ps
```

### 2. Run a Test

```bash
# Install test dependencies
uv pip install requests kafka-python

# Run the integration test
uv run python scripts/full_stack_test.py --test-url "https://arachne.test.dainst.org/entity/2003181"

# With custom timeout (default: 120 seconds)
uv run python scripts/full_stack_test.py --test-url "https://arachne.test.dainst.org/entity/2003181" --timeout 180
```

> **Note:** Currently only URLs from `arachne.test.dainst.org` are supported.

After the test completes, it will display:

- **Replay URL** (`/replay/{snapshot_id}`) — View the archived snapshot
- **Archive URL** (`/archive/{url_id}`) — View all snapshots for the URL

### 3. Access the Web Interface

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Browse all archived URLs and snapshots |
| `http://localhost:8000/replay/{snapshot_id}` | Replay a specific snapshot |
| `http://localhost:8000/archive/{url_id}` | View all snapshots for a URL |
| `http://localhost:8000/docs` | API documentation |

## Architecture

```text
User → Kafka → Orchestrator → Archive Generator → Web Interface
                                    ↓
                           Metadata Extractor → Web Interface
```

### Generated Artifacts

| Artifact | Description |
|----------|-------------|
| `archive.wacz` | Web archive for replay |
| `screenshot.png` | Full-page screenshot |
| `singlefile.html` | Self-contained HTML snapshot |
| `dom-snapshot.html` | Raw DOM snapshot |
| `metadata.json` | Extracted metadata (DataCite format) |
| `archive_generator_metadata.json` | Archive generation metadata |

## Common Commands

```bash
# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f orchestrator

# Stop services
docker compose down

# Stop and remove all data
docker compose down -v
```

## Project Structure

```text
cviers_project/
├── civers_orchestrator/          # Workflow coordination
├── civers_archive_generator/     # Web archiving
├── civers_metadata_extractor/    # Metadata extraction
├── civers_archive_web_interface/ # Storage and web UI
├── configs/                      # Shared configuration
├── scripts/                      # Testing utilities
└── docker-compose.yml            # Full stack deployment
```

For detailed documentation on each component, see the README in their respective directories.
