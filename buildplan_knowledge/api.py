"""
BuildPlan Knowledge Tool — Public API

Three agent-independent entry points:
- index_workspace(workspace_path)
- search_knowledge(workspace_path, query, scope, top_k, filters)
- get_index_status(workspace_path)

V0.1: All functions take an explicit workspace_path.
      Main Agent maintains current_workspace via its own adapter.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import config
from .database import DatabaseManager
from .schemas import (
    FileIndexStatus,
    FileStatus,
    IndexWorkspaceResult,
    RetrievalResult,
)
from .workspace import WorkspaceScanner

logger = logging.getLogger(__name__)


# ── index_workspace ───────────────────────────────────────────────────────

def index_workspace(workspace_path: str) -> IndexWorkspaceResult:
    """
    Scan the workspace, discover supported files, and update the SQLite index.

    For Phase B: only scans and records files in SQLite.
    No parsing, chunking, embedding, or vector store operations yet.
    """
    ws_path = Path(workspace_path).resolve()
    if not ws_path.is_dir():
        return IndexWorkspaceResult(
            workspace_path=str(ws_path),
            workspace_id="",
            discovered=0,
            indexed=0,
            skipped=0,
            failed=0,
            total_chunks=0,
            files=[],
        )

    scanner = WorkspaceScanner(ws_path)
    discovered = scanner.scan()

    result = IndexWorkspaceResult(
        workspace_path=str(ws_path),
        workspace_id="",
        discovered=len(discovered),
    )

    with DatabaseManager(ws_path) as db:
        result.workspace_id = db.get_or_create_workspace_id()

        # Build a set of currently existing relative paths
        existing_paths: set[str] = {f.relative_path for f in discovered}

        # Remove DB records for files that no longer exist
        for db_file in db.get_all_files():
            if db_file["relative_path"] not in existing_paths:
                db.delete_file(db_file["relative_path"])
                logger.info("Removed deleted file from index: %s", db_file["relative_path"])

        # Process each discovered file
        for disc in discovered:
            existing = db.get_file_by_path(disc.relative_path)

            # Upsert the file record
            db.upsert_file(
                document_id=disc.document_id,
                relative_path=disc.relative_path,
                file_name=disc.file_name,
                file_type=disc.file_type,
                file_size=disc.file_size,
                file_hash=disc.file_hash,
                modified_time=disc.modified_time,
            )

            # Check if re-indexing is needed
            if existing and existing["file_hash"] == disc.file_hash:
                # Hash unchanged — skip
                db.mark_skipped(disc.relative_path)
                result.skipped += 1
                result.files.append(FileStatus(
                    relative_path=disc.relative_path,
                    file_name=disc.file_name,
                    status=FileIndexStatus.SKIPPED,
                    chunk_count=existing.get("chunk_count", 0),
                ))
                logger.debug("Skipped (unchanged): %s", disc.relative_path)
            else:
                # New or changed — will need full indexing (Phase C+)
                # Phase B: scan-only, mark as indexed with chunk_count=0
                # When parsers are implemented, parse→chunk→embed happens here
                db.mark_indexed(disc.relative_path, chunk_count=0)
                result.indexed += 1
                result.files.append(FileStatus(
                    relative_path=disc.relative_path,
                    file_name=disc.file_name,
                    status=FileIndexStatus.INDEXED,
                    chunk_count=0,
                ))
                logger.info("Recorded: %s", disc.relative_path)

    logger.info("index_workspace complete: discovered=%d, indexed=%d, skipped=%d, failed=%d",
                result.discovered, result.indexed, result.skipped, result.failed)
    return result


# ── search_knowledge ──────────────────────────────────────────────────────

def search_knowledge(
    workspace_path: str,
    query: str,
    scope: str = "workspace",
    top_k: int = config.TOP_K_DEFAULT,
    filters: dict | None = None,
) -> RetrievalResult:
    """
    Search the knowledge base and return top-K evidence.

    Phase B: NOT YET IMPLEMENTED — returns empty result.
    Will be implemented in Phase E/F after embedding and vector store are ready.
    """
    logger.warning("search_knowledge not yet implemented (Phase B)")
    return RetrievalResult(query=query, scope=scope)


# ── get_index_status ──────────────────────────────────────────────────────

def get_index_status(workspace_path: str) -> dict:
    """
    Return the current index status for a workspace.

    Returns a dict with:
    - workspace_id
    - workspace_path
    - discovered_files (total in DB)
    - indexed_files
    - skipped_files (currently same as indexed for Phase B)
    - failed_files
    - total_chunks
    - files: list of per-file status
    """
    ws_path = Path(workspace_path).resolve()

    with DatabaseManager(ws_path) as db:
        ws_id = db.get_or_create_workspace_id()
        stats = db.get_stats()
        all_files = db.get_all_files()

        file_details = []
        for f in all_files:
            if f["indexed"]:
                status = "indexed"
            elif f["error_message"]:
                status = "failed"
            else:
                status = "pending"
            file_details.append({
                "relative_path": f["relative_path"],
                "file_name": f["file_name"],
                "file_type": f["file_type"],
                "file_size": f["file_size"],
                "file_hash": f["file_hash"],
                "status": status,
                "chunk_count": f["chunk_count"],
                "indexed_at": f["indexed_at"],
                "error_message": f["error_message"],
            })

    return {
        "workspace_id": ws_id,
        "workspace_path": str(ws_path),
        "discovered_files": stats["total_files"],
        "indexed_files": stats["indexed_files"],
        "failed_files": stats["failed_files"],
        "total_chunks": stats["total_chunks"],
        "files": file_details,
    }
