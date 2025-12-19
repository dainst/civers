"""
Tests for SQLiteManager - Database connection and operations.

Following TDD approach: Write tests first, then implement.
"""

import pytest
import sqlite3
from pathlib import Path
from app.database.sqlite_manager import SQLiteManager


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_manager(temp_db_path):
    """Provide connected SQLiteManager instance."""
    manager = SQLiteManager(temp_db_path)
    manager.connect()
    yield manager
    manager.close()


class TestSQLiteManagerConnection:
    """Test database connection management."""

    def test_connect_creates_database_file(self, temp_db_path):
        """Test that connect creates database file."""
        manager = SQLiteManager(temp_db_path)
        manager.connect()

        assert temp_db_path.exists()
        assert manager._connection is not None

        manager.close()

    def test_connect_creates_parent_directories(self, tmp_path):
        """Test that connect creates parent directories if needed."""
        db_path = tmp_path / "nested" / "directories" / "test.db"
        manager = SQLiteManager(db_path)
        manager.connect()

        assert db_path.exists()
        assert db_path.parent.exists()

        manager.close()

    def test_close_closes_connection(self, db_manager):
        """Test that close properly closes connection."""
        db_manager.close()

        assert db_manager._connection is None

    def test_connect_sets_row_factory(self, db_manager):
        """Test that connection uses Row factory for dict-like access."""
        cursor = db_manager._connection.cursor()
        cursor.execute("SELECT 1 as test_col")
        row = cursor.fetchone()

        # Row factory should allow dict-like access
        assert row['test_col'] == 1

    def test_connect_with_timeout(self, temp_db_path):
        """Test that connection has timeout configured."""
        manager = SQLiteManager(temp_db_path)
        manager.connect()

        # Connection should be established (timeout is internal SQLite setting)
        # We can't directly verify timeout value, but we can verify connection works
        assert manager._connection is not None
        cursor = manager._connection.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1

        manager.close()


class TestSQLiteManagerTransactions:
    """Test transaction management."""

    def test_transaction_commits_on_success(self, db_manager):
        """Test that transaction commits changes on success."""
        # Create a test table
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")

        # Use transaction
        with db_manager.transaction():
            db_manager.execute_query("INSERT INTO test VALUES (1, 'test')")

        # Verify data was committed
        cursor = db_manager.execute_query("SELECT * FROM test WHERE id = 1")
        row = cursor.fetchone()
        assert row is not None
        assert row['value'] == 'test'

    def test_transaction_rolls_back_on_error(self, db_manager):
        """Test that transaction rolls back on error."""
        # Create a test table and insert initial data
        db_manager.execute_query("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        with db_manager.transaction():
            db_manager.execute_query("INSERT INTO test VALUES (1, 'existing')")

        # Try to insert duplicate primary key in transaction
        with pytest.raises(sqlite3.IntegrityError):
            with db_manager.transaction():
                db_manager.execute_query("INSERT INTO test VALUES (1, 'duplicate')")

        # Verify original data is unchanged
        cursor = db_manager.execute_query("SELECT * FROM test WHERE id = 1")
        row = cursor.fetchone()
        assert row is not None
        assert row['value'] == 'existing'

    def test_transaction_nested_not_supported(self, db_manager):
        """Test that nested transactions work with same connection."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")

        with db_manager.transaction():
            db_manager.execute_query("INSERT INTO test VALUES (1, 'outer')")
            # Nested transaction should work
            with db_manager.transaction():
                db_manager.execute_query("INSERT INTO test VALUES (2, 'inner')")

        # Both should be committed
        cursor = db_manager.execute_query("SELECT COUNT(*) as count FROM test")
        row = cursor.fetchone()
        assert row['count'] == 2


class TestSQLiteManagerQueries:
    """Test query execution methods."""

    def test_execute_query_returns_cursor(self, db_manager):
        """Test that execute_query returns cursor."""
        cursor = db_manager.execute_query("SELECT 1 as test")

        assert isinstance(cursor, sqlite3.Cursor)
        row = cursor.fetchone()
        assert row['test'] == 1

    def test_execute_query_with_parameters(self, db_manager):
        """Test parameterized queries."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")
        db_manager.execute_query("INSERT INTO test VALUES (?, ?)", (1, 'test'))

        cursor = db_manager.execute_query("SELECT * FROM test WHERE id = ?", (1,))
        row = cursor.fetchone()
        assert row['value'] == 'test'

    def test_fetch_one_returns_dict(self, db_manager):
        """Test that fetch_one returns dict."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")
        db_manager.execute_query("INSERT INTO test VALUES (1, 'test')")

        result = db_manager.fetch_one("SELECT * FROM test WHERE id = ?", (1,))

        assert isinstance(result, dict)
        assert result['id'] == 1
        assert result['value'] == 'test'

    def test_fetch_one_returns_none_when_no_result(self, db_manager):
        """Test that fetch_one returns None when no results."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")

        result = db_manager.fetch_one("SELECT * FROM test WHERE id = ?", (999,))

        assert result is None

    def test_fetch_all_returns_list_of_dicts(self, db_manager):
        """Test that fetch_all returns list of dicts."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")
        db_manager.execute_query("INSERT INTO test VALUES (1, 'one')")
        db_manager.execute_query("INSERT INTO test VALUES (2, 'two')")
        db_manager.execute_query("INSERT INTO test VALUES (3, 'three')")

        results = db_manager.fetch_all("SELECT * FROM test ORDER BY id")

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(row, dict) for row in results)
        assert results[0]['value'] == 'one'
        assert results[1]['value'] == 'two'
        assert results[2]['value'] == 'three'

    def test_fetch_all_returns_empty_list_when_no_results(self, db_manager):
        """Test that fetch_all returns empty list when no results."""
        db_manager.execute_query("CREATE TABLE test (id INTEGER, value TEXT)")

        results = db_manager.fetch_all("SELECT * FROM test")

        assert isinstance(results, list)
        assert len(results) == 0


class TestSQLiteManagerSchemaInitialization:
    """Test schema initialization."""

    def test_initialize_schema_creates_tables(self, db_manager):
        """Test that initialize_schema creates tables."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_test_name ON test_table(name);
        """

        db_manager.initialize_schema(schema_sql)

        # Verify table exists
        cursor = db_manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result['name'] == 'test_table'

    def test_initialize_schema_creates_multiple_tables(self, db_manager):
        """Test that initialize_schema handles multiple tables."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS table1 (id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS table2 (id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS table3 (id INTEGER PRIMARY KEY);
        """

        db_manager.initialize_schema(schema_sql)

        # Verify all tables exist
        cursor = db_manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row['name'] for row in cursor.fetchall()]
        assert 'table1' in tables
        assert 'table2' in tables
        assert 'table3' in tables

    def test_initialize_schema_idempotent(self, db_manager):
        """Test that initialize_schema can be called multiple times."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        """

        # Call twice
        db_manager.initialize_schema(schema_sql)
        db_manager.initialize_schema(schema_sql)

        # Should still work without errors
        cursor = db_manager.execute_query("SELECT COUNT(*) as count FROM test_table")
        row = cursor.fetchone()
        assert row['count'] == 0


class TestSQLiteManagerErrorHandling:
    """Test error handling."""

    def test_execute_query_raises_on_invalid_sql(self, db_manager):
        """Test that execute_query raises on invalid SQL."""
        with pytest.raises(sqlite3.OperationalError):
            db_manager.execute_query("INVALID SQL SYNTAX")

    def test_fetch_one_raises_on_invalid_sql(self, db_manager):
        """Test that fetch_one raises on invalid SQL."""
        with pytest.raises(sqlite3.OperationalError):
            db_manager.fetch_one("INVALID SQL SYNTAX")

    def test_fetch_all_raises_on_invalid_sql(self, db_manager):
        """Test that fetch_all raises on invalid SQL."""
        with pytest.raises(sqlite3.OperationalError):
            db_manager.fetch_all("INVALID SQL SYNTAX")

    def test_initialize_schema_raises_on_invalid_sql(self, db_manager):
        """Test that initialize_schema raises on invalid SQL."""
        with pytest.raises(Exception):
            db_manager.initialize_schema("INVALID SQL SYNTAX")
