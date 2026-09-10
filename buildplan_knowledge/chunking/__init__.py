"""
BuildPlan Knowledge Tool — Document Chunking

Splits ParsedDocument elements into Chunks for embedding.
Strategy:
  - Heading boundary is a hard semantic boundary — NO overlap across different heading_path
  - Overlap only occurs within the same heading_path when a section exceeds target_chars
  - Tables are atomic (never split across chunks)
  - embedding_text format: "章节：heading1 > heading2 > ...\n\n<text>"

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
    → "章节：施工组织设计 > 第一章 工程概况\n\n"
    """
    if not heading_path:
        return ""
    return "章节：" + " > ".join(heading_path) + "\n\n"


@dataclass
class _ChunkBuffer:
    """Internal accumulator for building a single chunk."""
    elements_text: list[str]       # raw text of each element in this chunk
    heading_path: list[str]        # heading context for this chunk
    heading_only: bool = False     # True if buffer only contains a heading (no body yet)

    @property
    def total_chars(self) -> int:
        return sum(len(t) for t in self.elements_text)

    def build_texts(self) -> tuple[str, str]:
        """
        Return (text, embedding_text) for this buffer.

        - text: plain concatenated element texts
        - embedding_text: "章节：heading_path\n\n" + text
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

    Overlap rules:
      - Heading boundary = hard break, NO overlap across different heading_path
      - Overlap only within same heading_path when section exceeds target_chars

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

    def flush_buffer(allow_overlap: bool = False) -> None:
        """
        Finalize the current buffer into a Chunk.

        Args:
            allow_overlap: If True, save tail text for the NEXT chunk.
                           Only valid when the next chunk has the same heading_path.
        """
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

        if allow_overlap:
            # Keep tail for the next chunk (same heading_path only)
            tail = _get_overlap_tail(buffer.elements_text, overlap_chars)
            buffer.elements_text.clear()
            if tail:
                buffer.elements_text.append(tail)
        else:
            buffer.elements_text.clear()

    def start_new_section(heading_path: list[str]) -> None:
        """Start a fresh section with a new heading_path. No overlap carry-over."""
        buffer.elements_text.clear()
        buffer.heading_path = list(heading_path)

    for elem in parsed.elements:
        # ── Table: always atomic ────────────────────────────────────────
        if elem.element_type == ElementType.TABLE:
            # If buffer only has a heading (no body text), skip the title-only chunk.
            # The table chunk already carries the heading_path.
            if buffer.heading_only:
                buffer.elements_text.clear()
                buffer.heading_only = False
            else:
                # Flush current section (no overlap — table is a boundary)
                flush_buffer(allow_overlap=False)

            # Table gets its own chunk
            text, embedding_text = _build_table_chunk_text(elem)
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

            # Start fresh after table
            start_new_section(elem.heading_path)
            continue

        # ── Heading: hard semantic boundary ─────────────────────────────
        if elem.element_type == ElementType.HEADING:
            # Always flush with NO overlap — heading boundary is hard
            flush_buffer(allow_overlap=False)
            buffer.heading_path = list(elem.heading_path)
            buffer.elements_text.append(elem.text)
            buffer.heading_only = True   # mark: only heading so far, no body
            continue

        # ── Regular paragraph ───────────────────────────────────────────
        elem_text = elem.text
        if not elem_text:
            continue

        # Heading_path changed — hard boundary, no overlap
        if elem.heading_path != buffer.heading_path:
            flush_buffer(allow_overlap=False)
            buffer.heading_path = list(elem.heading_path)

        # Exceeds target size — split within same section, allow overlap
        if buffer.total_chars + len(elem_text) > target_chars and buffer.total_chars > 0:
            flush_buffer(allow_overlap=True)
            # heading_path stays the same (we're within the same section)

        buffer.elements_text.append(elem_text)
        buffer.heading_only = False  # now has body content

    # Final flush — no overlap needed
    flush_buffer(allow_overlap=False)

    logger.info(
        "Chunked document %s: %d elements -> %d chunks",
        parsed.file_name, len(parsed.elements), len(chunks),
    )
    return chunks


def _get_overlap_tail(elements_text: list[str], overlap_chars: int) -> str:
    """Get the tail of the buffer text for overlap within the same section."""
    full_text = "\n".join(elements_text)
    if len(full_text) <= overlap_chars:
        return full_text
    return full_text[-overlap_chars:]


def _build_table_chunk_text(elem: DocumentElement) -> tuple[str, str]:
    """Build text and embedding_text for a table chunk."""
    prefix = _make_heading_prefix(elem.heading_path)
    text = elem.text
    embedding_text = prefix + text if prefix else text
    return text, embedding_text
