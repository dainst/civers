"""
Tests for database schema models.

Following TDD approach: Write tests first, then implement.
"""

import pytest
from app.database.models import get_schema_sql, get_schema_version, SCHEMA_VERSION
from app.database.sqlite_manager import SQLiteManager


@pytest.fixture
def db_manager(tmp_path):
    """Provide SQLiteManager with initialized schema."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(db_path)
    manager.connect()

    # Initialize schema
    schema_sql = get_schema_sql()
    manager.initialize_schema(schema_sql)

    yield manager
    manager.close()


class TestSchemaVersion:
    """Test schema versioning."""

    def test_schema_version_constant_exists(self):
        """Test that SCHEMA_VERSION constant exists."""
        assert SCHEMA_VERSION is not None
        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION >= 1

    def test_get_schema_version_returns_version(self):
        """Test that get_schema_version returns version number."""
        version = get_schema_version()
        assert version == SCHEMA_VERSION
        assert isinstance(version, int)


class TestSchemaSQL:
    """Test schema SQL generation."""

    def test_get_schema_sql_returns_string(self):
        """Test that get_schema_sql returns SQL string."""
        schema = get_schema_sql()
        assert isinstance(schema, str)
        assert len(schema) > 0

    def test_schema_contains_urls_table(self):
        """Test that schema includes urls table."""
        schema = get_schema_sql()
        assert 'CREATE TABLE IF NOT EXISTS urls' in schema
        assert 'url_id TEXT PRIMARY KEY' in schema
        assert 'original_url TEXT NOT NULL' in schema
        assert 'folder_name TEXT NOT NULL' in schema

    def test_schema_contains_snapshots_table(self):
        """Test that schema includes snapshots table."""
        schema = get_schema_sql()
        assert 'CREATE TABLE IF NOT EXISTS snapshots' in schema
        assert 'snapshot_id TEXT PRIMARY KEY' in schema
        assert 'url_id TEXT NOT NULL' in schema
        assert 'timestamp TIMESTAMP NOT NULL' in schema
        assert 'FOREIGN KEY (url_id) REFERENCES urls(url_id)' in schema

    def test_schema_contains_artifacts_table(self):
        """Test that schema includes artifacts table."""
        schema = get_schema_sql()
        assert 'CREATE TABLE IF NOT EXISTS artifacts' in schema
        assert 'snapshot_id TEXT NOT NULL' in schema
        assert 'artifact_type TEXT NOT NULL' in schema
        assert 'file_path TEXT NOT NULL' in schema
        assert 'FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id)' in schema

    def test_schema_contains_indexes(self):
        """Test that schema includes performance indexes."""
        schema = get_schema_sql()
        assert 'CREATE INDEX IF NOT EXISTS idx_snapshots_url_id' in schema
        assert 'CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp' in schema
        assert 'CREATE INDEX IF NOT EXISTS idx_artifacts_snapshot_id' in schema

    def test_schema_contains_metadata_table(self):
        """Test that schema includes schema_metadata table."""
        schema = get_schema_sql()
        assert 'CREATE TABLE IF NOT EXISTS schema_metadata' in schema
        assert "INSERT OR IGNORE INTO schema_metadata" in schema


class TestSchemaInitialization:
    """Test schema initialization in database."""

    def test_schema_creates_urls_table(self, db_manager):
        """Test that urls table is created."""
        result = db_manager.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='urls'"
        )
        assert result is not None
        assert result['name'] == 'urls'

    def test_schema_creates_snapshots_table(self, db_manager):
        """Test that snapshots table is created."""
        result = db_manager.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'"
        )
        assert result is not None
        assert result['name'] == 'snapshots'

    def test_schema_creates_artifacts_table(self, db_manager):
        """Test that artifacts table is created."""
        result = db_manager.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'"
        )
        assert result is not None
        assert result['name'] == 'artifacts'

    def test_schema_creates_indexes(self, db_manager):
        """Test that indexes are created."""
        indexes = db_manager.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = [idx['name'] for idx in indexes]

        assert 'idx_snapshots_url_id' in index_names
        assert 'idx_snapshots_timestamp' in index_names
        assert 'idx_artifacts_snapshot_id' in index_names

    def test_schema_metadata_table_populated(self, db_manager):
        """Test that schema_metadata table has version."""
        result = db_manager.fetch_one(
            "SELECT value FROM schema_metadata WHERE key = 'version'"
        )
        assert result is not None
        assert int(result['value']) == SCHEMA_VERSION


class TestURLsTableStructure:
    """Test urls table structure and operations."""

    def test_insert_url_record(self, db_manager):
        """Test inserting a URL record."""
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 0))

        result = db_manager.fetch_one("SELECT * FROM urls WHERE url_id = ?", ('example_com',))
        assert result is not None
        assert result['url_id'] == 'example_com'
        assert result['original_url'] == 'https://example.com'
        assert result['folder_name'] == 'example_com'
        assert result['snapshot_count'] == 0

    def test_url_id_is_primary_key(self, db_manager):
        """Test that url_id is primary key (no duplicates)."""
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 0))

        # Try to insert duplicate
        with pytest.raises(Exception):
            with db_manager.transaction():
                db_manager.execute_query("""
                    INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                    VALUES (?, ?, ?, ?)
                """, ('example_com', 'https://example2.com', 'example_com', 0))

    def test_url_timestamps_auto_populate(self, db_manager):
        """Test that created_at and updated_at timestamps are set."""
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 0))

        result = db_manager.fetch_one("SELECT * FROM urls WHERE url_id = ?", ('example_com',))
        assert result['created_at'] is not None
        assert result['updated_at'] is not None


class TestSnapshotsTableStructure:
    """Test snapshots table structure and operations."""

    def test_insert_snapshot_record(self, db_manager):
        """Test inserting a snapshot record."""
        # First insert URL
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 1))

            db_manager.execute_query("""
                INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                VALUES (?, ?, ?, ?, ?)
            """, ('20240101_120000', 'example_com', '2024-01-01T12:00:00',
                  'https://example.com', '/path/to/snapshot'))

        result = db_manager.fetch_one(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            ('20240101_120000',)
        )
        assert result is not None
        assert result['snapshot_id'] == '20240101_120000'
        assert result['url_id'] == 'example_com'

    def test_snapshot_foreign_key_constraint(self, db_manager):
        """Test that snapshot requires valid url_id."""
        # Try to insert snapshot without URL
        with pytest.raises(Exception):
            with db_manager.transaction():
                db_manager.execute_query("""
                    INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                    VALUES (?, ?, ?, ?, ?)
                """, ('20240101_120000', 'nonexistent_url', '2024-01-01T12:00:00',
                      'https://example.com', '/path'))

    def test_snapshot_cascade_delete(self, db_manager):
        """Test that deleting URL cascades to snapshots."""
        # Insert URL and snapshot
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 1))

            db_manager.execute_query("""
                INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                VALUES (?, ?, ?, ?, ?)
            """, ('20240101_120000', 'example_com', '2024-01-01T12:00:00',
                  'https://example.com', '/path'))

        # Delete URL
        with db_manager.transaction():
            db_manager.execute_query("DELETE FROM urls WHERE url_id = ?", ('example_com',))

        # Verify snapshot is also deleted
        result = db_manager.fetch_one(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            ('20240101_120000',)
        )
        assert result is None


class TestArtifactsTableStructure:
    """Test artifacts table structure and operations."""

    def test_insert_artifact_record(self, db_manager):
        """Test inserting an artifact record."""
        # Insert URL and snapshot first
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 1))

            db_manager.execute_query("""
                INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                VALUES (?, ?, ?, ?, ?)
            """, ('20240101_120000', 'example_com', '2024-01-01T12:00:00',
                  'https://example.com', '/path'))

            db_manager.execute_query("""
                INSERT INTO artifacts (snapshot_id, artifact_type, file_path, file_size)
                VALUES (?, ?, ?, ?)
            """, ('20240101_120000', 'archive.wacz', '/path/archive.wacz', 1024))

        result = db_manager.fetch_one(
            "SELECT * FROM artifacts WHERE snapshot_id = ? AND artifact_type = ?",
            ('20240101_120000', 'archive.wacz')
        )
        assert result is not None
        assert result['artifact_type'] == 'archive.wacz'
        assert result['file_path'] == '/path/archive.wacz'
        assert result['file_size'] == 1024

    def test_artifact_unique_constraint(self, db_manager):
        """Test that snapshot_id + artifact_type is unique."""
        # Insert URL, snapshot, and artifact
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 1))

            db_manager.execute_query("""
                INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                VALUES (?, ?, ?, ?, ?)
            """, ('20240101_120000', 'example_com', '2024-01-01T12:00:00',
                  'https://example.com', '/path'))

            db_manager.execute_query("""
                INSERT INTO artifacts (snapshot_id, artifact_type, file_path, file_size)
                VALUES (?, ?, ?, ?)
            """, ('20240101_120000', 'archive.wacz', '/path/archive.wacz', 1024))

        # Try to insert duplicate
        with pytest.raises(Exception):
            with db_manager.transaction():
                db_manager.execute_query("""
                    INSERT INTO artifacts (snapshot_id, artifact_type, file_path, file_size)
                    VALUES (?, ?, ?, ?)
                """, ('20240101_120000', 'archive.wacz', '/path/other.wacz', 2048))

    def test_artifact_cascade_delete(self, db_manager):
        """Test that deleting snapshot cascades to artifacts."""
        # Insert URL, snapshot, and artifact
        with db_manager.transaction():
            db_manager.execute_query("""
                INSERT INTO urls (url_id, original_url, folder_name, snapshot_count)
                VALUES (?, ?, ?, ?)
            """, ('example_com', 'https://example.com', 'example_com', 1))

            db_manager.execute_query("""
                INSERT INTO snapshots (snapshot_id, url_id, timestamp, url, folder_path)
                VALUES (?, ?, ?, ?, ?)
            """, ('20240101_120000', 'example_com', '2024-01-01T12:00:00',
                  'https://example.com', '/path'))

            db_manager.execute_query("""
                INSERT INTO artifacts (snapshot_id, artifact_type, file_path, file_size)
                VALUES (?, ?, ?, ?)
            """, ('20240101_120000', 'archive.wacz', '/path/archive.wacz', 1024))

        # Delete snapshot
        with db_manager.transaction():
            db_manager.execute_query(
                "DELETE FROM snapshots WHERE snapshot_id = ?",
                ('20240101_120000',)
            )

        # Verify artifact is also deleted
        result = db_manager.fetch_one(
            "SELECT * FROM artifacts WHERE snapshot_id = ?",
            ('20240101_120000',)
        )
        assert result is None
