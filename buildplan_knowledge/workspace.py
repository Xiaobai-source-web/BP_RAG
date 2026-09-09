"""
BuildPlan Knowledge Tool — Workspace Scanner

Scans a workspace directory, discovers supported files,
and reports file status for incremental indexing.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredFile:
    """A file found during workspace scanning."""
    absolute_path: Path
    relative_path: str
    file_name: str
    file_type: str
    file_size: int
    file_hash: str
    modified_time: float
    document_id: str


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _should_ignore(dir_name: str) -> bool:
    """Check if a directory name should be ignored."""
    return dir_name in config.IGNORED_DIRS or dir_name.startswith(".")


class WorkspaceScanner:
    """
    Scans a workspace directory for supported files.

    Respects ignore rules and filters by supported extensions.
    """

    def __init__(self, workspace_path: str | Path):
        self.workspace_path = Path(workspace_path).resolve()

        if not self.workspace_path.is_dir():
            raise ValueError(f"Workspace path does not exist: {self.workspace_path}")

    def scan(self) -> list[DiscoveredFile]:
        """
        Walk the workspace and return all supported files.

        Returns:
            List of DiscoveredFile, sorted by relative_path.
        """
        discovered: list[DiscoveredFile] = []

        for file_path in self._walk_workspace():
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            if suffix not in config.SUPPORTED_EXTENSIONS:
                continue

            try:
                stat = file_path.stat()
                relative_path = str(file_path.relative_to(self.workspace_path)).replace("\\", "/")
                file_hash = _compute_file_hash(file_path)

                discovered.append(DiscoveredFile(
                    absolute_path=file_path,
                    relative_path=relative_path,
                    file_name=file_path.name,
                    file_type=suffix,
                    file_size=stat.st_size,
                    file_hash=file_hash,
                    modified_time=stat.st_mtime,
                    document_id=str(uuid.uuid4()),
                ))
            except (OSError, PermissionError) as e:
                logger.warning("Cannot access file %s: %s", file_path, e)

        discovered.sort(key=lambda f: f.relative_path)
        logger.info("Workspace scan complete: %d files discovered in %s",
                     len(discovered), self.workspace_path)
        return discovered

    def _walk_workspace(self):
        """
        Yield all file paths under the workspace, skipping ignored directories.
        """
        stack = [self.workspace_path]

        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except PermissionError:
                logger.warning("Permission denied: %s", current)
                continue

            for entry in entries:
                if entry.is_dir():
                    if not _should_ignore(entry.name):
                        stack.append(entry)
                elif entry.is_file():
                    yield entry
