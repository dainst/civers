"""
SQLite database manager for connection and query operations.

Provides connection management, transaction handling, and query execution
for the SQLite-based storage provider.
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class SQLiteManager:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: Path):
        """
        Initialize SQLite manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """
        Establish database connection.

        Creates parent directories if needed and configures connection
        with Row factory for dict-like access.

        Raises:
            Exception: If connection fails
        """
        try:
            # Create parent directories if needed
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connection with configuration
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow use across threads
                timeout=10.0  # Connection timeout in seconds
            )

            # Enable Row factory for dict-like access
            self._connection.row_factory = sqlite3.Row

            # Enable foreign key constraints
            self._connection.execute("PRAGMA foreign_keys = ON")

            logger.info(f"Connected to SQLite: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Closed database connection")

    @contextmanager
    def transaction(self):
        """
        Context manager for transactions.

        Commits on success, rolls back on error.

        Yields:
            sqlite3.Connection: Database connection

        Example:
            with db_manager.transaction():
                db_manager.execute_query("INSERT INTO ...")
        """
        try:
            yield self._connection
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Transaction failed, rolled back: {e}")
            raise

    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute SQL query.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            sqlite3.Cursor: Query cursor

        Raises:
            Exception: If query execution fails
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            return cursor
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """
        Fetch one result as dictionary.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            Dict or None: First result as dict, or None if no results

        Raises:
            Exception: If query execution fails
        """
        cursor = self.execute_query(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """
        Fetch all results as list of dictionaries.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            List[Dict]: All results as list of dicts

        Raises:
            Exception: If query execution fails
        """
        cursor = self.execute_query(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def initialize_schema(self, schema_sql: str) -> None:
        """
        Create database schema.

        Executes schema SQL script to create tables and indexes.

        Args:
            schema_sql: SQL script with CREATE TABLE/INDEX statements

        Raises:
            Exception: If schema initialization fails
        """
        try:
            self._connection.executescript(schema_sql)
            self._connection.commit()
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise

    def apply_migrations(self) -> None:
        """
        Apply incremental schema migrations for columns added after initial creation.

        Uses PRAGMA table_info to detect missing columns and applies ALTER TABLE
        to add them without touching existing data.
        """
        migrations: list[tuple[str, str, str]] = [
            # (table, column, column_definition)
            ("request_status", "workflow_name", "TEXT"),
        ]

        for table, column, definition in migrations:
            existing = {
                row[1]
                for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if column not in existing:
                self._connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
                self._connection.commit()
                logger.info(f"Migration applied: added column '{column}' to '{table}'")
