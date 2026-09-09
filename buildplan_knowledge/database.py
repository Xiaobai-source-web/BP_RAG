"""
BuildPlan Knowledge Tool — SQLite Database Layer

Handles:
- Workspace ID (UUID) persistence
- File tracking (the "file ledger")
- Schema creation and migration
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .schemas import FileIndexStatus, FileStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages the SQLite database for a single workspace."""

    def __init__(self, workspace_path: str | Path):
        self.workspace_path = Path(workspace_path).resolve()
        self.db_path = config.get_db_path(self.workspace_path)
        self._conn: sqlite3.Connection | None = None

    # ── Connection management ─────────────────────────────────────────────

    def connect(self) -> None:
        """Open (or create) the database and ensure schema exists."""
        buildplan_dir = config.get_buildplan_dir(self.workspace_path)
        buildplan_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        logger.info("Database connected: %s", self.db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("DatabaseManager not connected. Call connect() first.")
        return self._conn

    # ── Schema ────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id     TEXT NOT NULL UNIQUE,
                relative_path   TEXT NOT NULL UNIQUE,
                file_name       TEXT NOT NULL,
                file_type       TEXT NOT NULL,
                file_size       INTEGER,
                file_hash       TEXT NOT NULL,
                modified_time   REAL,
                indexed         INTEGER DEFAULT 0,
                indexed_at      TEXT,
                chunk_count     INTEGER DEFAULT 0,
                parser_version  TEXT DEFAULT 'v0.1',
                error_message   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_files_hash
                ON files(file_hash);

            CREATE INDEX IF NOT EXISTS idx_files_indexed
                ON files(indexed);
        """)

    # ── Workspace ID (UUID) ───────────────────────────────────────────────

    def get_or_create_workspace_id(self) -> str:
        """
        Return the stable workspace UUID.

        On first call, generates a new UUID and persists it to
        .buildplan/workspace.json. On subsequent calls, reads from disk.
        """
        meta_path = config.get_workspace_meta_path(self.workspace_path)

        if meta_path.exists():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            ws_id = data.get("workspace_id")
            if ws_id:
                return ws_id

        # First time — generate and persist
        ws_id = str(uuid.uuid4())
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps({"workspace_id": ws_id}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Created workspace_id %s for %s", ws_id, self.workspace_path)
        return ws_id

    # ── File operations ───────────────────────────────────────────────────

    def upsert_file(
        self,
        *,
        document_id: str,
        relative_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        file_hash: str,
        modified_time: float,
    ) -> None:
        """Insert or update a file record."""
        self.conn.execute(
            """
            INSERT INTO files
                (document_id, relative_path, file_name, file_type,
                 file_size, file_hash, modified_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                document_id   = excluded.document_id,
                file_name     = excluded.file_name,
                file_type     = excluded.file_type,
                file_size     = excluded.file_size,
                file_hash     = excluded.file_hash,
                modified_time = excluded.modified_time,
                indexed       = 0,
                indexed_at    = NULL,
                chunk_count   = 0,
                error_message = NULL
            """,
            (document_id, relative_path, file_name, file_type,
             file_size, file_hash, modified_time),
        )
        self.conn.commit()

    def mark_indexed(self, relative_path: str, chunk_count: int) -> None:
        """Mark a file as successfully indexed."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE files
            SET indexed = 1, indexed_at = ?, chunk_count = ?, error_message = NULL
            WHERE relative_path = ?
            """,
            (now, chunk_count, relative_path),
        )
        self.conn.commit()

    def mark_failed(self, relative_path: str, error_message: str) -> None:
        """Mark a file as failed during indexing."""
        self.conn.execute(
            """
            UPDATE files
            SET indexed = 0, error_message = ?
            WHERE relative_path = ?
            """,
            (error_message, relative_path),
        )
        self.conn.commit()

    def mark_skipped(self, relative_path: str) -> None:
        """Mark a file as skipped (hash unchanged, no re-index needed)."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE files
            SET indexed = 1, indexed_at = ?, error_message = NULL
            WHERE relative_path = ?
            """,
            (now, relative_path),
        )
        self.conn.commit()

    def get_file_by_path(self, relative_path: str) -> dict | None:
        """Get a file record by its relative path."""
        row = self.conn.execute(
            "SELECT * FROM files WHERE relative_path = ?", (relative_path,)
        ).fetchone()
        return dict(row) if row else None

    def get_file_by_hash(self, file_hash: str) -> dict | None:
        """Get a file record by its hash (for dedup detection)."""
        row = self.conn.execute(
            "SELECT * FROM files WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_files(self) -> list[dict]:
        """Get all file records."""
        rows = self.conn.execute("SELECT * FROM files ORDER BY relative_path").fetchall()
        return [dict(r) for r in rows]

    def delete_file(self, relative_path: str) -> None:
        """Delete a file record."""
        self.conn.execute(
            "DELETE FROM files WHERE relative_path = ?", (relative_path,)
        )
        self.conn.commit()

    def get_indexed_files(self) -> list[dict]:
        """Get all successfully indexed file records."""
        rows = self.conn.execute(
            "SELECT * FROM files WHERE indexed = 1 ORDER BY relative_path"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return aggregate index statistics."""
        row = self.conn.execute("""
            SELECT
                COUNT(*)                            AS total_files,
                SUM(CASE WHEN indexed = 1 THEN 1 ELSE 0 END) AS indexed_files,
                SUM(CASE WHEN indexed = 0 AND error_message IS NOT NULL
                    THEN 1 ELSE 0 END)              AS failed_files,
                SUM(COALESCE(chunk_count, 0))       AS total_chunks
            FROM files
        """).fetchone()
        return dict(row)

    def delete_all(self) -> None:
        """Delete all file records (used for full re-index)."""
        self.conn.execute("DELETE FROM files")
        self.conn.commit()
