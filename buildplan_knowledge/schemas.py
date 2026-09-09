"""
BuildPlan Knowledge Tool — Data Schemas

All public-facing data structures. No third-party framework objects leak here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ── File status ───────────────────────────────────────────────────────────

class FileIndexStatus(str, Enum):
    """Status of a file in the index."""
    PENDING = "pending"
    INDEXED = "indexed"
    SKIPPED = "skipped"      # hash unchanged
    FAILED = "failed"


# ── Document element (Parser output) ─────────────────────────────────────

class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"


@dataclass
class DocumentElement:
    """A single structural element from a parsed document."""
    element_type: ElementType
    text: str
    level: int | None = None          # heading level (1-9), None for non-headings
    heading_path: list[str] = field(default_factory=list)  # full heading ancestry
    metadata: dict = field(default_factory=dict)            # e.g. table rows


@dataclass
class ParsedDocument:
    """Output of a Parser (DOCX, PDF, etc.)."""
    document_id: str
    file_name: str
    relative_path: str
    file_type: str
    elements: list[DocumentElement] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ── Chunk ─────────────────────────────────────────────────────────────────

@dataclass
class ChunkMetadata:
    """Metadata attached to every chunk."""
    workspace_id: str
    document_id: str
    file_name: str
    relative_path: str
    file_type: str
    heading_path: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """A single chunk ready for embedding."""
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str                        # original text, always preserved
    embedding_text: str              # text + heading context for embedding
    heading_path: list[str] = field(default_factory=list)
    metadata: ChunkMetadata | None = None


# ── Retrieval ─────────────────────────────────────────────────────────────

@dataclass
class DocumentSource:
    """Source information for a retrieval result."""
    document_id: str
    file_name: str
    relative_path: str
    heading_path: list[str] = field(default_factory=list)


@dataclass
class RetrievalItem:
    """A single retrieval result."""
    chunk_id: str
    text: str
    score: float
    source: DocumentSource


@dataclass
class RetrievalResult:
    """Result of a search_knowledge() call."""
    query: str
    scope: str
    results: list[RetrievalItem] = field(default_factory=list)


# ── Index workspace ──────────────────────────────────────────────────────

@dataclass
class FileStatus:
    """Status of a single file after indexing."""
    relative_path: str
    file_name: str
    status: FileIndexStatus
    chunk_count: int = 0
    error_message: str | None = None


@dataclass
class IndexWorkspaceResult:
    """Result of an index_workspace() call."""
    workspace_path: str
    workspace_id: str
    discovered: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    total_chunks: int = 0
    files: list[FileStatus] = field(default_factory=list)
