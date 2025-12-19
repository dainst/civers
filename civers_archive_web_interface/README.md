# Civers Web Interface

The Civers Web Interface is a web application for browsing, managing, and replaying archived versions of websites. It provides:

- **URL Archives** – Browse all snapshots of archived URLs with associated artifacts (WACZ archives, screenshots, SingleFile HTML, metadata)
- **Snapshot Replay** – Replay archived snapshots with metadata display and citation generation (APA, MLA, Chicago)
- **File Upload API** – Upload archive files programmatically
- **Fast Queries** – Choose between filesystem or SQLite-indexed storage

## ✨ Features

- **Two Storage Providers**
  - Filesystem: Direct file access
  - SQLite: Database-indexed for faster queries
- **File Upload API** – Upload WACZ archives and artifacts
- **Auto-Indexing** – SQLite provider automatically indexes files on startup
- **RESTful API** – Full API for integration
- **Citation Generation** – Multiple citation formats
- **Configurable** – YAML-based configuration

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

### 2. Configure Storage

Create your configuration file:

```bash
# Copy example configuration
cp config.example.yaml config.yaml
```

**Basic configuration** (`config.yaml`):
```yaml
storage:
  type: "sqlite"  # Use "filesystem" for direct file access

  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true

  filesystem:
    path: "archives"
```

See [Configuration](#configuration) section for more details.

### 3. Run the Application

```bash
# Development mode (with auto-reload)
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Alternative: Run as module
uv run python -m app.main
```

The application will be available at:
- **Main application**: http://127.0.0.1:8000
- **API documentation**: http://127.0.0.1:8000/docs
- **Health check**: http://127.0.0.1:8000/health

### 4. Test File Upload

Upload test files to verify everything works:

```bash
# Quick test with Python script
python test_upload.py
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

## Configuration

The application uses a YAML configuration file (`config.yaml`) to configure storage providers and other settings.

### Storage Provider Options

You can choose between two storage providers:

#### Filesystem Provider

**How it works:**
- Scans filesystem directories on every request
- Reads files directly from disk
- No database required

**Benefits:**
- No setup or indexing needed
- Always reflects current filesystem state
- Simple and straightforward
- Great for development

**Use when:**
- Developing locally
- Working with small archives
- You want simplicity

**Configuration:**
```yaml
storage:
  type: "filesystem"
  filesystem:
    path: "archives"
    timeout_seconds: 10
```

#### SQLite Provider (Recommended)

**How it works:**
- Maintains a database index of all files
- Queries database for fast lookups
- Auto-indexes filesystem on first startup
- Updates index when new files are uploaded

**Benefits:**
- Faster than traversing filesystem and caching on every request
- Queries database instead of scanning directories
- Automatically builds index from existing files
- Best for production environments

**Use when:**
- Running in production
- Working with larger archives
- You need fast query performance

**Configuration:**
```yaml
storage:
  type: "sqlite"
  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true  # Rebuild index if database is empty
    connection_timeout: 10
  filesystem:
    path: "archives"  # Still needs path for file storage
```

### Full Configuration Example

```yaml
storage:
  type: "sqlite"

  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true
    connection_timeout: 10

  filesystem:
    path: "archives"
    timeout_seconds: 10

  cache:
    ttl_seconds: 60
    max_entries: 1000

validation:
  snapshot_id_pattern: '^req_[a-zA-Z0-9\-_]+_\d{8}_\d{6}$'
  allowed_artifact_types:
    - "archive.wacz"
    - "metadata.json"
    - "screenshot.png"
    - "singlefile.html"
```

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

This will:
- Create test files (WACZ, metadata, screenshot, SingleFile HTML)
- Upload them to the API
- Verify the upload
- Display results

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
- `GET /api/urls` - List all archived URLs (with pagination and sorting)
- `GET /api/urls/{url_id}/snapshots` - List snapshots for a specific URL
- `GET /api/snapshots/{snapshot_id}` - Get snapshot details
- `GET /api/snapshots/{snapshot_id}/artifacts/{type}` - Download artifact file
- `POST /api/upload` - Upload archive files
- `GET /health` - Application health check

### Web Pages
- `GET /` - Home page
- `GET /archive/{url_id}` - URL archive list page
- `GET /replay/{snapshot_id}` - Snapshot replay page

### API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Usage Examples

```bash
# List all archived URLs
curl "http://127.0.0.1:8000/api/urls"

# List snapshots for a specific URL
curl "http://127.0.0.1:8000/api/urls/example_com_home_page/snapshots"

# Get snapshot details
curl "http://127.0.0.1:8000/api/snapshots/req_test-1_20240301_120000"

# Download artifact
curl "http://127.0.0.1:8000/api/snapshots/req_test-1_20240301_120000/artifacts/archive.wacz" \
  -o archive.wacz

# Filter snapshots by artifact availability
curl "http://127.0.0.1:8000/api/urls/example_com/snapshots?has_wacz=true"

# Filter snapshots by date range
curl "http://127.0.0.1:8000/api/urls/example_com/snapshots?from_date=2024-01-01&to_date=2024-12-31"
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

# Bash script alternative
./test_upload.sh
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
│   ├── api/                # API endpoints
│   ├── database/           # SQLite database management
│   ├── models/             # Pydantic data models
│   ├── storage/            # Storage providers and services
│   ├── cli/               # CLI commands
│   └── main.py            # FastAPI application
├── tests/                  # Unit and integration tests
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JavaScript, images
├── data/                   # SQLite database files
├── config.yaml            # Application configuration
├── config.example.yaml    # Example configuration
├── test_upload.py         # Upload test script
└── test_upload.sh         # Bash upload test script
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

```bash
# Application settings
HOST=127.0.0.1
PORT=8000
DEBUG=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
JSON_LOGGING=true

# Configuration
CONFIG_PATH=config.yaml  # Optional, defaults to config.yaml
```

## Storage Provider Details

### How Each Provider Works

**Filesystem Provider:**
1. Request comes in for URLs/snapshots
2. Scans `archives/` directory structure
3. Reads metadata.json files
4. Returns results
5. Caches results temporarily

**SQLite Provider:**
1. On startup: Checks if database exists
2. If empty and `auto_rebuild=true`: Scans filesystem and populates database
3. Request comes in for URLs/snapshots
4. Queries database index (fast)
5. Returns results
6. On upload: Updates database automatically

### Database Schema (SQLite)

When using SQLite provider:
- **urls** - Stores archived URLs
- **snapshots** - Stores snapshot metadata
- **artifacts** - Stores artifact file information
- **Indexes** - On timestamps, URL IDs for fast queries

### Switching Providers

You can switch between providers by changing the `config.yaml` file. No data migration needed - both providers read from the same filesystem.

```yaml
# Switch to filesystem
storage:
  type: "filesystem"

# Switch to SQLite
storage:
  type: "sqlite"
  sqlite:
    db_path: "data/archives.db"
    auto_rebuild: true
```

Restart the application for changes to take effect.

## Troubleshooting

### Application won't start

**Error**: `Configuration loading failed`
- Check `config.yaml` syntax (valid YAML)
- Verify file paths exist
- Ensure proper indentation

### Upload fails

**Error**: `Could not connect to API`
- Ensure application is running: `uvicorn app.main:app --reload`
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
- Check `auto_rebuild: true` in config
- Manually rebuild: Delete `data/archives.db` and restart

### Files not found

**Error**: `Snapshot not found` or `404`
- Verify files exist in `archives/` directory
- Check directory structure matches expected format
- If using SQLite, rebuild index: delete `data/archives.db` and restart with `auto_rebuild: true`

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
