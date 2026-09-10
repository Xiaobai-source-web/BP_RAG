"""
BuildPlan Knowledge Tool — DOCX Parser

Parses .docx files using python-docx, preserving document structure:
- Headings (with level and heading_path)
- Paragraphs
- Tables (converted to text representation)

V0.1: Embedded images are skipped with a warning.
"""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..schemas import DocumentElement, ElementType, ParsedDocument
from .base import BaseParser

logger = logging.getLogger(__name__)

# ── Heading style name prefixes used by Word ─────────────────────────────
# Word styles like "Heading 1", "Heading 2", etc.
# Also handle Chinese: "标题 1", "标题 2"
_HEADING_STYLE_PREFIXES = ("Heading", "标题", "heading")


def _get_heading_level(paragraph: Paragraph) -> int | None:
    """
    Detect if a paragraph is a heading and return its level (1-9).

    Checks:
    1. Style name starts with "Heading" / "标题" followed by a digit
    2. Paragraph outline level (pPr outlineLvl)

    Returns None if not a heading.
    """
    # Check style name
    style = paragraph.style
    if style and style.name:
        style_name = style.name.strip()
        for prefix in _HEADING_STYLE_PREFIXES:
            if style_name.startswith(prefix):
                # Extract level number after prefix
                suffix = style_name[len(prefix):].strip()
                if suffix and suffix[0].isdigit():
                    level = int(suffix[0])
                    if 1 <= level <= 9:
                        return level

    # Check outline level from XML (more reliable for some documents)
    try:
        pPr = paragraph._element.pPr
        if pPr is not None:
            outline_lvl = pPr.find(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl"
            )
            if outline_lvl is not None:
                val = outline_lvl.get(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
                )
                if val is not None:
                    level = int(val) + 1  # outlineLvl is 0-indexed
                    if 1 <= level <= 9:
                        return level
    except (AttributeError, ValueError):
        pass

    return None


def _table_to_text(table: Table) -> str:
    """
    Convert a table to a markdown-style text representation.

    Format:
        | cell1 | cell2 |
        | cell3 | cell4 |
    """
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)


def _has_images(paragraph: Paragraph) -> bool:
    """Check if a paragraph contains inline images."""
    # Look for drawing elements (inline images)
    drawings = paragraph._element.findall(
        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
    )
    if drawings:
        return True
    # Also check for pict elements (older Word format)
    picts = paragraph._element.findall(
        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"
    )
    return len(picts) > 0


class DocxParser(BaseParser):
    """
    DOCX document parser.

    Extracts structural elements (heading, paragraph, table) from .docx files
    while preserving document hierarchy via heading_path.
    """

    def parse(self, file_path: str | Path, document_id: str) -> ParsedDocument:
        """
        Parse a DOCX file into a ParsedDocument.

        Args:
            file_path: Path to the .docx file.
            document_id: Unique identifier for this document.

        Returns:
            ParsedDocument with ordered elements.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        doc = Document(str(file_path))

        parsed = ParsedDocument(
            document_id=document_id,
            file_name=file_path.name,
            relative_path="",  # caller should set this
            file_type=".docx",
        )

        # Track heading hierarchy for heading_path
        # heading_stack[level-1] = heading text
        heading_stack: list[str] = []

        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                # Paragraph element
                para = Paragraph(element, doc)
                self._process_paragraph(para, heading_stack, parsed)

            elif tag == "tbl":
                # Table element
                table = Table(element, doc)
                self._process_table(table, heading_stack, parsed)

            # Other elements (e.g., sectPr) are ignored

        logger.info(
            "Parsed DOCX: %s — %d elements (headings=%d, paragraphs=%d, tables=%d)",
            file_path.name,
            len(parsed.elements),
            sum(1 for e in parsed.elements if e.element_type == ElementType.HEADING),
            sum(1 for e in parsed.elements if e.element_type == ElementType.PARAGRAPH),
            sum(1 for e in parsed.elements if e.element_type == ElementType.TABLE),
        )

        return parsed

    def _process_paragraph(
        self,
        para: Paragraph,
        heading_stack: list[str],
        parsed: ParsedDocument,
    ) -> None:
        """Process a paragraph element: detect heading or regular paragraph."""
        text = para.text.strip()

        # Skip empty paragraphs (but preserve them as they may be meaningful)
        # Actually, skip truly empty ones to avoid noise
        if not text:
            return

        # Check for images
        if _has_images(para):
            logger.warning(
                "Paragraph contains images (skipping image, keeping text): %s...",
                text[:50],
            )

        level = _get_heading_level(para)

        if level is not None:
            # This is a heading — update heading_stack
            # Truncate stack to current level (remove deeper headings)
            while len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(text)

            parsed.elements.append(DocumentElement(
                element_type=ElementType.HEADING,
                text=text,
                level=level,
                heading_path=list(heading_stack),
            ))
        else:
            # Regular paragraph
            parsed.elements.append(DocumentElement(
                element_type=ElementType.PARAGRAPH,
                text=text,
                level=None,
                heading_path=list(heading_stack),
            ))

    def _process_table(
        self,
        table: Table,
        heading_stack: list[str],
        parsed: ParsedDocument,
    ) -> None:
        """Process a table element: convert to text and record metadata."""
        table_text = _table_to_text(table)

        # Extract row data for metadata
        rows_data = []
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells]
            rows_data.append(row_cells)

        parsed.elements.append(DocumentElement(
            element_type=ElementType.TABLE,
            text=table_text,
            level=None,
            heading_path=list(heading_stack),
            metadata={
                "rows": len(table.rows),
                "columns": len(table.columns),
                "data": rows_data,
            },
        ))
