# Civers Web Interface

The Civers Web Interface is a web application for browsing, managing, and replaying archived versions of websites. It provides:

- **URL Archives** – Browse all snapshots of archived URLs with associated artifacts (WACZ archives, screenshots, SingleFile HTML, metadata)
- **Snapshot Replay** – Replay archived snapshots with metadata display and citation generation (APA, MLA, Chicago)
- **Archive Request** – Submit new archive requests through the web form, processed via Kafka
- **File Upload API** – Upload archive files programmatically
- **Fast Queries** – Choose between filesystem or SQLite-indexed storage

## ✨ Features

- **Two Storage Providers**
  - Filesystem: Direct file access
  - SQLite: Database-indexed for faster queries
- **Archive Request Submission** – Web form for requesting new archives via Kafka
- **File Upload API** – Upload WACZ archives and artifacts
- **Auto-Indexing** – SQLite provider automatically indexes files on startup
- **RESTful API** – Full API for integration
- **Embeddable Widget** – JavaScript widget for embedding archive views
- **Citation Generation** – Multiple citation formats
- **Configurable** – Hierarchical YAML-based configuration with environment overrides

## Prerequisites

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) package manager

## Quick Start

### 1. Install Dependencies

```bash
# Install UV package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 2. Configuration

The application uses hierarchical YAML configuration files in `configs/data/`. Default settings are loaded from `configs/data/defaults/` and merged with environment-specific overrides from `configs/data/environments/`.

Key configuration files:

| File | Purpose |
|------|---------|
| `configs/data/defaults/app.yaml` | Application metadata, logging, API settings |
| `configs/data/defaults/server.yaml` | Server host, port, debug mode, CORS origins |
| `configs/data/defaults/storage.yaml` | Storage provider selection and settings |
| `configs/data/defaults/validation.yaml` | Input validation rules, allowed artifact types |
| `configs/data/defaults/kafka.yaml` | Kafka transport configuration |
| `configs/data/defaults/domains.yaml` | Domain-specific archiving rules |

See [docs/components/CONFIGURATION.md](docs/components/CONFIGURATION.md) for full configuration reference.

### 3. Run the Application

```bash
# Development mode (with auto-reload)
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Alternative: Run as module
uv run python -m app.main
```

The application will be available at:

- **Main application**: <http://127.0.0.1:8000>
- **API documentation**: <http://127.0.0.1:8000/docs>
- **Health check**: <http://127.0.0.1:8000/health>

### 4. Test File Upload

Upload test files to verify everything works:

```bash
# Quick test with Python script
uv run python test_upload.py
```

See [File Upload](#file-upload) section for more options.

### 5. Run Tests

```bash
# Run all tests
uv run python -m pytest

# Run tests with verbose output
uv run python -m pytest -v

# Run specific test file
uv run python -m pytest tests/test_snapshots_api.py -v
```

## Storage Providers

You can choose between two storage providers via `configs/data/defaults/storage.yaml`:

### Filesystem Provider

**How it works:**

- Scans filesystem directories on every request
- Reads files directly from disk
- No database required

**Use when:**

- Developing locally
- Working with small archives
- You want simplicity

**Configuration** (`storage.yaml`):

```yaml
storage:
  type: "filesystem"
  filesystem:
    path: "archives"
    timeout_seconds: 0
```

### SQLite Provider (Recommended)

**How it works:**

- Maintains a database index of all files
- Queries database for fast lookups
- Auto-indexes filesystem on first startup
- Updates index when new files are uploaded

**Use when:**

- Running in production
- Working with larger archives
- You need fast query performance

**Configuration** (`storage.yaml`):

```yaml
storage:
  type: "sqlite"
  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true
    connection_timeout: 10
  filesystem:
    path: "archives"  # Still needs path for file storage
```

### Switching Providers

Change the `type` in `configs/data/defaults/storage.yaml`. No data migration needed — both providers read from the same filesystem. Restart the application for changes to take effect.

## File Upload

The application provides an API endpoint for uploading archive files.

### Quick Test

Use the provided test script:

```bash
# Basic upload test
python test_upload.py

# Custom URL
python test_upload.py --url https://example.com/my-page

# Custom request ID
python test_upload.py --request-id my-test-123
```

### Manual Upload with curl

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "url=https://example.com/test" \
  -F "request_id=test-123" \
  -F "files=@archive.wacz" \
  -F "files=@metadata.json" \
  -F "files=@screenshot.png" \
  -F "files=@singlefile.html"
```

### Expected Response

```json
{
  "success": true,
  "snapshot_id": "req_test-123_20250112_143022",
  "url": "https://example.com/test",
  "artifacts_uploaded": [
    "archive.wacz",
    "metadata.json",
    "screenshot.png",
    "singlefile.html"
  ],
  "message": "Successfully uploaded 4 files"
}
```

### Verify Upload

**Check via API:**

```bash
# List all URLs
curl http://localhost:8000/api/urls

# Get specific snapshot
curl http://localhost:8000/api/snapshots/req_test-123_20250112_143022
```

**Check filesystem:**

```bash
ls -la archives/example_com/test/req_test-123_20250112_143022/
```

**Check database (SQLite):**

```bash
sqlite3 data/archives.db "SELECT * FROM snapshots ORDER BY created_at DESC LIMIT 5;"
```

## Available API Endpoints

### Core APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/urls` | List all archived URLs (pagination, sorting) |
| `GET` | `/api/url/{url_id}` | Get details for a specific URL |
| `GET` | `/api/urls/{url_id}/snapshots` | List snapshots for a URL |
| `GET` | `/api/snapshots/{snapshot_id}` | Get snapshot details |
| `GET` | `/api/artifacts/serve` | Download an artifact file |
| `POST` | `/api/upload` | Upload archive files |
| `GET` | `/api/upload` | Upload endpoint info |
| `POST` | `/api/archive-request` | Submit a new archive request |
| `GET` | `/api/request-status/{request_id}` | Check archive request status |
| `POST` | `/api/webhook/status` | Receive status updates from orchestrator |
| `GET` | `/health` | Application health check |

### Widget

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/widget/civers-widget.js` | Embeddable widget JavaScript |
| `GET` | `/widget/civers-widget.css` | Widget styles |
| `GET` | `/widget/demo.html` | Widget demo page |

### Web Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page |
| `GET` | `/archive-request` | Archive request form |
| `GET` | `/my-requests` | User's archive requests |
| `GET` | `/status/{request_id}` | Request status page |
| `GET` | `/archive/{url_id}` | URL archive list page |
| `GET` | `/replay/{snapshot_id}` | Snapshot replay page |

### API Documentation

- **Swagger UI**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>

## API Usage Examples

```bash
# List all archived URLs
curl "http://127.0.0.1:8000/api/urls"

# List snapshots for a specific URL
curl "http://127.0.0.1:8000/api/urls/example_com_home_page/snapshots"

# Get snapshot details
curl "http://127.0.0.1:8000/api/snapshots/req_test-1_20240301_120000"

# Download artifact
curl "http://127.0.0.1:8000/api/artifacts/serve?snapshot_id=req_test-1_20240301_120000&type=archive.wacz" \
  -o archive.wacz

# Filter snapshots by artifact availability
curl "http://127.0.0.1:8000/api/urls/example_com/snapshots?has_wacz=true"

# Filter snapshots by date range
curl "http://127.0.0.1:8000/api/urls/example_com/snapshots?from_date=2024-01-01&to_date=2024-12-31"

# Submit archive request
curl -X POST "http://127.0.0.1:8000/api/archive-request" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "domain": "example.com"}'
```

## Testing

### Unit Tests

```bash
# Run all tests
uv run python -m pytest

# Run with verbose output
uv run python -m pytest -v

# Run specific test file
uv run python -m pytest tests/test_snapshots_api.py -v

# Run with coverage
uv run python -m pytest --cov=app
```

### File Upload Test

```bash
# Automated test script
python test_upload.py

# With custom options
python test_upload.py --url https://example.com --request-id test-123
```

### Manual API Testing

```bash
# Health check
curl http://localhost:8000/health

# List URLs
curl http://localhost:8000/api/urls

# Upload file
curl -X POST http://localhost:8000/api/upload \
  -F "url=https://example.com" \
  -F "request_id=test" \
  -F "files=@archive.wacz"
```

## Development Setup

### Project Structure

```
civers_archive_web_interface/
├── app/
│   ├── api/                # API endpoint routers
│   ├── custom_exceptions/  # Custom exception classes
│   ├── database/           # SQLite database management
│   ├── logging/            # Logging configuration
│   ├── middleware/         # Security and error-handling middleware
│   ├── models/             # Pydantic data models
│   ├── routes/             # Web page routes (templates)
│   ├── services/           # Business logic services (Kafka, etc.)
│   ├── storage/            # Storage providers and services
│   ├── utils/              # Utility functions
│   └── main.py             # FastAPI application entry point
├── configs/
│   ├── __init__.py         # Package exports and public API
│   ├── models.py           # Configuration Pydantic models
│   ├── loaders.py          # YAML configuration loader
│   └── data/
│       ├── defaults/       # Base YAML configuration files
│       └── environments/   # Environment-specific overrides
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JavaScript, images
├── tests/                  # Unit and integration tests
├── data/                   # SQLite database files (runtime)
└── test_upload.py          # Upload test script
```

### Storage Structure

The application expects archived data in this format:

```
archives/
├── {domain}/                    # e.g., example_com
│   └── {path_segment}/         # e.g., home_page
│       └── req_{id}_{timestamp}/   # e.g., req_test-1_20240301_120000/
│           ├── metadata.json       # Archive metadata
│           ├── archive.wacz        # Web Archive Collection
│           ├── screenshot.png      # Page screenshot
│           └── singlefile.html     # SingleFile HTML
```

### Environment Variables

The application primarily uses YAML configuration files. The following environment variables are supported:

| Variable | Description |
|----------|-------------|
| `CONFIG_ENVIRONMENT` | Override environment detection (`development`, `testing`, `docker`) |
| `CONFIG_DIR` | Override configuration directory path |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker connection string (used via `${...}` expansion in YAML) |

### Database Schema (SQLite)

When using the SQLite provider:

- **urls** – Stores archived URLs
- **snapshots** – Stores snapshot metadata
- **artifacts** – Stores artifact file information
- **Indexes** – On timestamps, URL IDs for fast queries

## Troubleshooting

### Application won't start

**Error**: `Configuration validation failed`

- Check YAML syntax in `configs/data/defaults/` files
- Verify file paths exist
- Ensure proper indentation

### Upload fails

**Error**: `Could not connect to API`

- Ensure application is running: `uv run uvicorn app.main:app --reload`
- Check URL is correct: `http://localhost:8000/api/upload`

**Error**: `400 Bad Request`

- Verify URL is valid (starts with http:// or https://)
- Ensure request_id is provided
- Check at least one file is uploaded

### Database issues (SQLite)

**Error**: `Database locked`

- Close any SQLite browser connections
- Restart application

**Empty results after upload:**

- Check `auto_rebuild: true` in `configs/data/defaults/storage.yaml`
- Manually rebuild: Delete `data/archives.db` and restart

### Files not found

**Error**: `Snapshot not found` or `404`

- Verify files exist in `archives/` directory
- Check directory structure matches expected format
- If using SQLite, rebuild index: delete `data/archives.db` and restart with `auto_rebuild: true`
