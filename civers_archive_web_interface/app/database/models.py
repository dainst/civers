"""
Database table schemas for SQLite storage.

Defines the database structure for the SQLite-based storage provider,
including tables for URLs, snapshots, and artifacts with appropriate
indexes for performance.
"""

SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- URLs table
CREATE TABLE IF NOT EXISTS urls (
    url_id TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    first_captured TIMESTAMP,
    last_captured TIMESTAMP,
    snapshot_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Snapshots table
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    url_id TEXT NOT NULL,
    request_id TEXT,  -- Original request_id for deduplication (find existing snapshot)
    timestamp TIMESTAMP NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    folder_path TEXT NOT NULL,
    status_code INTEGER,
    content_type TEXT,
    content_length INTEGER,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (url_id) REFERENCES urls(url_id) ON DELETE CASCADE
);

-- Artifacts table
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    UNIQUE(snapshot_id, artifact_type)
);

-- Request status table for tracking archive requests
CREATE TABLE IF NOT EXISTS request_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, in_progress, completed, failed
    domain TEXT,
    url TEXT NOT NULL,
    current_step TEXT,
    completed_steps TEXT,  -- JSON array of step names
    error_message TEXT,
    callback_url TEXT,
    snapshot_id TEXT,  -- Link to snapshot when completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE SET NULL
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_url_id ON snapshots(url_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_request_id ON snapshots(request_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_status_code ON snapshots(status_code);
CREATE INDEX IF NOT EXISTS idx_artifacts_snapshot_id ON artifacts(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_urls_last_captured ON urls(last_captured DESC);

-- Status tracking indexes
CREATE INDEX IF NOT EXISTS idx_request_status_request_id ON request_status(request_id);
CREATE INDEX IF NOT EXISTS idx_request_status_status ON request_status(status);
CREATE INDEX IF NOT EXISTS idx_request_status_created_at ON request_status(created_at DESC);

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_metadata (key, value)
VALUES ('version', '3');

UPDATE schema_metadata SET value = '3' WHERE key = 'version';
"""


def get_schema_sql() -> str:
    """
    Get the SQL schema definition.

    Returns:
        str: Complete SQL schema for creating all tables and indexes
    """
    return SCHEMA_SQL


def get_schema_version() -> int:
    """
    Get the current schema version.

    Returns:
        int: Schema version number
    """
    return SCHEMA_VERSION
