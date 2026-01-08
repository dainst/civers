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

The project uses a **Makefile** to simplify Docker operations.

**Development Mode** (Hot-reload + local code mounts):

```bash
make dev
```

**Production Mode** (Runs built images):

```bash
make prod
```

**Verify status**:

```bash
make ps
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

## Monorepo Management

This project uses a monorepo structure managed with **Git Subtree**. This allows us to maintain a unified codebase while keeping the ability to sync changes with independent standalone repositories.

### 1. Setup Remotes (One-time)

If you are a maintainer who needs to sync sub-components with their standalone repositories, add the following remotes:

```bash
git remote add remote-archive-generator git@github.com:dainst/civers_archive_generator.git
git remote add remote-web-interface git@github.com:dainst/civers_archive_web_interface.git
git remote add remote-metadata-extractor git@github.com:dainst/civers_metadata_extractor.git
git remote add remote-orchestrator git@github.com:dainst/civers_orchestrator.git
```

### 2. Pushing Changes to Standalone Repos

When you make changes in the monorepo and want to push them to a component's standalone repository:

```bash
# Example: Pushing changes for the web interface
git subtree push --prefix=civers_archive_web_interface remote-web-interface main
```

### 3. Pulling Changes from Standalone Repos

To bring in changes made directly in a standalone repository:

```bash
git fetch remote-web-interface
git subtree pull --prefix=civers_archive_web_interface remote-web-interface main --squash
```

### 4. Working on Features

1. Create a new branch in the monorepo.
2. Make changes across any components.
3. Commit your changes normally.
4. Use the `subtree push` commands above to sync specific components to their remotes.

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
