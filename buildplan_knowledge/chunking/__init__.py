"""
BuildPlan Knowledge Tool — Document Chunking

Splits ParsedDocument elements into Chunks for embedding.
Strategy:
  - Respects document structure (heading boundaries)
  - Tables are atomic (never split across chunks)
  - Each chunk's embedding_text includes heading context
  - Overlap between consecutive chunks for continuity

V0.1: Character-based size approximation (1 token ≈ 1.5 Chinese chars).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from .. import config
from ..schemas import Chunk, ChunkMetadata, DocumentElement, ElementType, ParsedDocument

logger = logging.getLogger(__name__)


def _make_heading_prefix(heading_path: list[str]) -> str:
    """
    Build a context prefix from the heading path.

    Example: ["施工组织设计", "第一章 工程概况"]
    → "[施工组织设计 > 第一章 工程概况] "
    """
    if not heading_path:
        return ""
    return "[" + " > ".join(heading_path) + "] "


@dataclass
class _ChunkBuffer:
    """Internal accumulator for building a single chunk."""
    elements_text: list[str]       # raw text of each element in this chunk
    heading_path: list[str]        # heading context for this chunk
    is_table_chunk: bool = False   # True if this chunk is a single table

    @property
    def total_chars(self) -> int:
        return sum(len(t) for t in self.elements_text)

    def build_texts(self) -> tuple[str, str]:
        """
        Return (text, embedding_text) for this buffer.

        - text: plain concatenated element texts
        - embedding_text: heading prefix + concatenated text
        """
        text = "\n".join(self.elements_text)
        prefix = _make_heading_prefix(self.heading_path)
        embedding_text = prefix + text if prefix else text
        return text, embedding_text


def chunk_document(
    parsed: ParsedDocument,
    workspace_id: str,
    target_chars: int = config.CHUNK_TARGET_CHARS,
    overlap_chars: int = config.CHUNK_OVERLAP_CHARS,
) -> list[Chunk]:
    """
    Split a ParsedDocument into Chunks.

    Args:
        parsed: Output from a parser (DocxParser, etc.).
        workspace_id: Workspace UUID for metadata.
        target_chars: Target chunk size in characters.
        overlap_chars: Overlap between consecutive chunks in characters.

    Returns:
        List of Chunk objects ready for embedding.
    """
    if not parsed.elements:
        return []

    chunks: list[Chunk] = []
    buffer = _ChunkBuffer(elements_text=[], heading_path=[])

    def flush_buffer() -> None:
        """Finalize the current buffer into a Chunk."""
        if not buffer.elements_text:
            return
        text, embedding_text = buffer.build_texts()
        chunk = Chunk(
            chunk_id=str(uuid.uuid4()),
            document_id=parsed.document_id,
            chunk_index=len(chunks),
            text=text,
            embedding_text=embedding_text,
            heading_path=list(buffer.heading_path),
            metadata=ChunkMetadata(
                workspace_id=workspace_id,
                document_id=parsed.document_id,
                file_name=parsed.file_name,
                relative_path=parsed.relative_path,
                file_type=parsed.file_type,
                heading_path=list(buffer.heading_path),
            ),
        )
        chunks.append(chunk)
        buffer.elements_text.clear()

    def get_overlap_text() -> str:
        """Get the tail of the current buffer for overlap."""
        if not buffer.elements_text:
            return ""
        full_text = "\n".join(buffer.elements_text)
        if len(full_text) <= overlap_chars:
            return full_text
        return full_text[-overlap_chars:]

    for elem in parsed.elements:
        # ── Table: always atomic ────────────────────────────────────────
        if elem.element_type == ElementType.TABLE:
            # Flush current buffer first
            flush_buffer()

            # Tables go into their own chunk (never split)
            text, embedding_text = _build_table_chunk_text(elem, parsed)
            chunk = Chunk(
                chunk_id=str(uuid.uuid4()),
                document_id=parsed.document_id,
                chunk_index=len(chunks),
                text=text,
                embedding_text=embedding_text,
                heading_path=list(elem.heading_path),
                metadata=ChunkMetadata(
                    workspace_id=workspace_id,
                    document_id=parsed.document_id,
                    file_name=parsed.file_name,
                    relative_path=parsed.relative_path,
                    file_type=parsed.file_type,
                    heading_path=list(elem.heading_path),
                ),
            )
            chunks.append(chunk)

            # Start fresh buffer after table
            buffer.heading_path = list(elem.heading_path)
            continue

        # ── Heading: may start a new chunk ──────────────────────────────
        if elem.element_type == ElementType.HEADING:
            # Flush if buffer is getting large
            if buffer.total_chars > 0:
                flush_buffer()
            buffer.heading_path = list(elem.heading_path)
            buffer.elements_text.append(elem.text)
            continue

        # ── Regular paragraph ───────────────────────────────────────────
        elem_text = elem.text
        if not elem_text:
            continue

        # Update heading path if it changed
        if elem.heading_path != buffer.heading_path:
            # If buffer is non-empty and heading context changed, flush
            if buffer.total_chars > 0:
                flush_buffer()
                # Apply overlap from previous chunk
                overlap = get_overlap_text()
                if overlap:
                    buffer.elements_text.append(overlap)
            buffer.heading_path = list(elem.heading_path)

        # Check if adding this element would exceed target
        if buffer.total_chars + len(elem_text) > target_chars and buffer.total_chars > 0:
            flush_buffer()
            # Apply overlap
            overlap = get_overlap_text()
            if overlap:
                buffer.elements_text.append(overlap)
            buffer.heading_path = list(elem.heading_path)

        buffer.elements_text.append(elem_text)

    # Flush remaining buffer
    flush_buffer()

    logger.info(
        "Chunked document %s: %d elements → %d chunks",
        parsed.file_name, len(parsed.elements), len(chunks),
    )
    return chunks


def _build_table_chunk_text(elem: DocumentElement, parsed: ParsedDocument) -> tuple[str, str]:
    """Build text and embedding_text for a table chunk."""
    prefix = _make_heading_prefix(elem.heading_path)
    text = elem.text
    embedding_text = prefix + text if prefix else text
    return text, embedding_text
