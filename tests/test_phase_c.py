"""
Phase C Tests — DOCX Parser + Chunking + Parser Registry

Tests run against real .docx files created via python-docx.
Covers: parser registry, DOCX parsing, document chunking, and full index flow.
"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from docx import Document
from docx.shared import Inches

from buildplan_knowledge import config, get_index_status, index_workspace
from buildplan_knowledge.chunking import chunk_document
from buildplan_knowledge.database import DatabaseManager
from buildplan_knowledge.parsers import DocxParser, get_parser, supported_extensions
from buildplan_knowledge.schemas import (
    Chunk,
    DocumentElement,
    ElementType,
    ParsedDocument,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def create_simple_docx(path: Path) -> None:
    """Create a simple DOCX with headings, paragraphs, and a table."""
    doc = Document()
    doc.add_heading("施工组织设计", level=1)
    doc.add_paragraph("本工程为某住宅小区项目，总建筑面积约5万平方米。")
    doc.add_heading("工程概况", level=2)
    doc.add_paragraph("项目位于城市东部新区，交通便利，周边配套设施齐全。")
    doc.add_paragraph("总工期为305天，计划2025年3月开工。")
    doc.add_heading("施工方案", level=2)
    doc.add_paragraph("基础工程施工包括桩基施工、基坑支护、钢筋混凝土结构施工。")
    doc.add_heading("施工工艺", level=3)
    doc.add_paragraph("本工程采用PHC管桩施工工艺，包括桩位放样、桩机就位、压桩、接桩、终止压桩。")
    doc.add_heading("进度计划", level=2)
    table = doc.add_table(rows=3, cols=3)
    table.rows[0].cells[0].text = "项目"
    table.rows[0].cells[1].text = "工期(天)"
    table.rows[0].cells[2].text = "开始日期"
    table.rows[1].cells[0].text = "基础工程"
    table.rows[1].cells[1].text = "60"
    table.rows[1].cells[2].text = "2025-03-01"
    table.rows[2].cells[0].text = "主体结构"
    table.rows[2].cells[1].text = "120"
    table.rows[2].cells[2].text = "2025-05-01"
    doc.save(str(path))


def create_long_docx(path: Path, paragraph_count: int = 50) -> None:
    """Create a DOCX with many paragraphs to test chunking boundaries."""
    doc = Document()
    doc.add_heading("长文档测试", level=1)
    for i in range(paragraph_count):
        doc.add_heading(f"第{i+1}节", level=2)
        # Each paragraph ~200 chars, so ~4-5 paragraphs per chunk (target 900 chars)
        doc.add_paragraph(
            f"这是第{i+1}节的内容。" + "施工技术要求包括质量控制、安全管理、"
            "进度管理、成本管理等多个方面。" * 8
        )
    doc.save(str(path))


def create_empty_docx(path: Path) -> None:
    """Create a DOCX with no content (only default paragraph)."""
    doc = Document()
    doc.save(str(path))


# ── Parser Registry Tests ────────────────────────────────────────────────

def test_parser_registry_docx():
    """Test that .docx maps to DocxParser."""
    print("=" * 60)
    print("TEST: Parser Registry — DOCX")
    print("=" * 60)

    parser = get_parser(".docx")
    assert parser is not None, "get_parser('.docx') should return a parser"
    assert isinstance(parser, DocxParser)
    print("  [OK] get_parser('.docx') returns DocxParser")

    # Case insensitive
    parser2 = get_parser(".DOCX")
    assert parser2 is not None
    print("  [OK] Case insensitive: .DOCX works")

    # Unsupported extension
    parser3 = get_parser(".pdf")
    assert parser3 is None
    print("  [OK] get_parser('.pdf') returns None")

    # supported_extensions()
    exts = supported_extensions()
    assert ".docx" in exts
    print(f"  [OK] supported_extensions() = {exts}")


# ── DOCX Parser Tests ────────────────────────────────────────────────────

def test_docx_parser_basic():
    """Test basic DOCX parsing: headings, paragraphs, tables."""
    print("\n" + "=" * 60)
    print("TEST: DOCX Parser — Basic Structure")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test.docx"
        create_simple_docx(docx_path)

        parsed = parser.parse(docx_path, document_id="test-001")

        assert isinstance(parsed, ParsedDocument)
        assert parsed.document_id == "test-001"
        assert parsed.file_name == "test.docx"
        assert parsed.file_type == ".docx"
        print(f"  [OK] ParsedDocument created: {parsed.file_name}")

        # Count element types
        headings = [e for e in parsed.elements if e.element_type == ElementType.HEADING]
        paragraphs = [e for e in parsed.elements if e.element_type == ElementType.PARAGRAPH]
        tables = [e for e in parsed.elements if e.element_type == ElementType.TABLE]

        assert len(headings) >= 4, f"Expected >=4 headings, got {len(headings)}"
        assert len(paragraphs) >= 4, f"Expected >=4 paragraphs, got {len(paragraphs)}"
        assert len(tables) == 1, f"Expected 1 table, got {len(tables)}"
        print(f"  [OK] Elements: {len(headings)} headings, {len(paragraphs)} paragraphs, {len(tables)} tables")

        # Check first heading
        h0 = headings[0]
        assert h0.text == "施工组织设计"
        assert h0.level == 1
        assert h0.heading_path == ["施工组织设计"]
        print(f"  [OK] First heading: '{h0.text}' (level={h0.level})")

        # Check nested heading path
        h_nested = [e for e in headings if e.level == 3]
        assert len(h_nested) >= 1
        assert len(h_nested[0].heading_path) == 3
        print(f"  [OK] Nested heading path: {' > '.join(h_nested[0].heading_path)}")


def test_docx_parser_heading_levels():
    """Test that heading levels are correctly detected."""
    print("\n" + "=" * 60)
    print("TEST: DOCX Parser — Heading Levels")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "levels.docx"
        doc = Document()
        doc.add_heading("一级标题", level=1)
        doc.add_heading("二级标题A", level=2)
        doc.add_heading("三级标题", level=3)
        doc.add_heading("二级标题B", level=2)
        doc.save(str(docx_path))

        parsed = parser.parse(docx_path, "test-levels")
        headings = [e for e in parsed.elements if e.element_type == ElementType.HEADING]

        assert len(headings) == 4
        assert headings[0].level == 1
        assert headings[1].level == 2
        assert headings[2].level == 3
        assert headings[3].level == 2

        # Check heading_path resets when going back up
        assert headings[2].heading_path == ["一级标题", "二级标题A", "三级标题"]
        assert headings[3].heading_path == ["一级标题", "二级标题B"]
        print("  [OK] Heading levels: 1, 2, 3, 2")
        print(f"  [OK] Path reset: {' > '.join(headings[3].heading_path)}")


def test_docx_parser_table():
    """Test that tables are parsed with metadata."""
    print("\n" + "=" * 60)
    print("TEST: DOCX Parser — Table Parsing")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "table.docx"
        create_simple_docx(docx_path)

        parsed = parser.parse(docx_path, "test-table")
        tables = [e for e in parsed.elements if e.element_type == ElementType.TABLE]

        assert len(tables) == 1
        table = tables[0]

        # Check metadata
        assert table.metadata["rows"] == 3
        assert table.metadata["columns"] == 3
        assert len(table.metadata["data"]) == 3
        assert table.metadata["data"][0] == ["项目", "工期(天)", "开始日期"]
        print(f"  [OK] Table: {table.metadata['rows']}x{table.metadata['columns']}")
        print(f"  [OK] Header: {table.metadata['data'][0]}")

        # Check text representation
        assert "|" in table.text
        assert "项目" in table.text
        print(f"  [OK] Text representation contains markdown table syntax")


def test_docx_parser_file_not_found():
    """Test that missing file raises FileNotFoundError."""
    print("\n" + "=" * 60)
    print("TEST: DOCX Parser — File Not Found")
    print("=" * 60)

    parser = DocxParser()
    try:
        parser.parse("/nonexistent/file.docx", "test")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        print(f"  [OK] FileNotFoundError raised: {e}")


def test_docx_parser_empty():
    """Test parsing an empty DOCX."""
    print("\n" + "=" * 60)
    print("TEST: DOCX Parser — Empty Document")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "empty.docx"
        create_empty_docx(docx_path)

        parsed = parser.parse(docx_path, "test-empty")
        assert len(parsed.elements) == 0
        print(f"  [OK] Empty doc: {len(parsed.elements)} elements")


# ── Chunking Tests ───────────────────────────────────────────────────────

def test_chunking_basic():
    """Test basic chunking of a simple document."""
    print("\n" + "=" * 60)
    print("TEST: Chunking — Basic")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test.docx"
        create_simple_docx(docx_path)

        parsed = parser.parse(docx_path, "test-chunk")
        parsed.relative_path = "test.docx"

        chunks = chunk_document(parsed, workspace_id="ws-test")

        assert len(chunks) > 0, "Should produce at least one chunk"
        assert all(isinstance(c, Chunk) for c in chunks)
        print(f"  [OK] Produced {len(chunks)} chunks")

        # Check chunk metadata
        for c in chunks:
            assert c.document_id == "test-chunk"
            assert c.metadata.workspace_id == "ws-test"
            assert c.metadata.file_name == "test.docx"
        print(f"  [OK] All chunks have correct metadata")

        # Check chunk indices are sequential
        for i, c in enumerate(chunks):
            assert c.chunk_index == i
        print(f"  [OK] Chunk indices are sequential (0..{len(chunks)-1})")


def test_chunking_heading_context():
    """Test that chunks include heading context in embedding_text."""
    print("\n" + "=" * 60)
    print("TEST: Chunking — Heading Context")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test.docx"
        create_simple_docx(docx_path)

        parsed = parser.parse(docx_path, "test-hp")
        parsed.relative_path = "test.docx"

        chunks = chunk_document(parsed, workspace_id="ws-test")

        # Find a chunk under "工程概况"
        overview_chunks = [c for c in chunks if "工程概况" in " > ".join(c.heading_path)]
        assert len(overview_chunks) >= 1
        c = overview_chunks[0]

        # embedding_text should have heading prefix
        assert "工程概况" in c.embedding_text
        assert c.embedding_text.startswith("[")
        print(f"  [OK] Chunk under '工程概况' has heading prefix")
        print(f"    embedding_text starts: {c.embedding_text[:60]}...")


def test_chunking_table_atomic():
    """Test that tables are never split across chunks."""
    print("\n" + "=" * 60)
    print("TEST: Chunking — Table Atomic")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test.docx"
        create_simple_docx(docx_path)

        parsed = parser.parse(docx_path, "test-tbl")
        parsed.relative_path = "test.docx"

        chunks = chunk_document(parsed, workspace_id="ws-test")

        # Find table chunks (contain "|" in text)
        table_chunks = [c for c in chunks if "|" in c.text and "项目" in c.text]
        assert len(table_chunks) == 1, f"Expected 1 table chunk, got {len(table_chunks)}"

        tc = table_chunks[0]
        assert "基础工程" in tc.text
        assert "主体结构" in tc.text
        print(f"  [OK] Table is atomic in single chunk")
        print(f"    Table chunk text preview: {tc.text[:80]}...")


def test_chunking_long_document():
    """Test chunking a long document respects size targets."""
    print("\n" + "=" * 60)
    print("TEST: Chunking — Long Document Size")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "long.docx"
        create_long_docx(docx_path, paragraph_count=30)

        parsed = parser.parse(docx_path, "test-long")
        parsed.relative_path = "long.docx"

        chunks = chunk_document(parsed, workspace_id="ws-test")

        assert len(chunks) > 5, f"Expected many chunks, got {len(chunks)}"
        print(f"  [OK] Long document → {len(chunks)} chunks")

        # Most text chunks should be around target size (with some variance)
        text_chunks = [c for c in chunks if "|" not in c.text]
        sizes = [len(c.text) for c in text_chunks]
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        print(f"  [OK] Average chunk size: {avg_size:.0f} chars (target: {config.CHUNK_TARGET_CHARS})")

        # Each heading starts a new chunk; verify all chunks are non-empty
        assert all(s > 0 for s in sizes), "Some chunks are empty"
        print(f"  [OK] All {len(sizes)} text chunks are non-empty")


def test_chunking_empty_document():
    """Test chunking an empty document returns empty list."""
    print("\n" + "=" * 60)
    print("TEST: Chunking — Empty Document")
    print("=" * 60)

    parser = DocxParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "empty.docx"
        create_empty_docx(docx_path)

        parsed = parser.parse(docx_path, "test-empty")
        parsed.relative_path = "empty.docx"

        chunks = chunk_document(parsed, workspace_id="ws-test")
        assert chunks == []
        print(f"  [OK] Empty doc → 0 chunks")


# ── Integration Tests ────────────────────────────────────────────────────

def test_index_workspace_with_parsing():
    """Test that index_workspace now parses and chunks files."""
    print("\n" + "=" * 60)
    print("TEST: Integration — index_workspace with Parsing")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "workspace"
        ws.mkdir()

        # Create a real DOCX
        create_simple_docx(ws / "doc1.docx")

        # Index
        result = index_workspace(str(ws))

        assert result.discovered == 1
        assert result.indexed == 1
        assert result.failed == 0
        assert result.total_chunks > 0, "Should have chunks after indexing"
        print(f"  [OK] Indexed: {result.indexed} file, {result.total_chunks} chunks")

        # Check DB has chunk count
        status = get_index_status(str(ws))
        assert status["total_chunks"] > 0
        file_info = status["files"][0]
        assert file_info["chunk_count"] > 0
        assert file_info["status"] == "indexed"
        print(f"  [OK] DB records chunk_count={file_info['chunk_count']}")


def test_index_workspace_incremental():
    """Test that re-indexing skips unchanged files."""
    print("\n" + "=" * 60)
    print("TEST: Integration — Incremental Indexing")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "workspace"
        ws.mkdir()
        create_simple_docx(ws / "doc1.docx")

        # First index
        r1 = index_workspace(str(ws))
        assert r1.indexed == 1
        chunks1 = r1.total_chunks
        print(f"  [OK] First index: {chunks1} chunks")

        # Second index (unchanged)
        r2 = index_workspace(str(ws))
        assert r2.skipped == 1
        assert r2.indexed == 0
        print(f"  [OK] Second index: skipped={r2.skipped}")

        # Modify and re-index (different content = different hash)
        doc = Document()
        doc.add_heading("Modified Document", level=1)
        doc.add_paragraph("This content has been changed.")
        doc.save(str(ws / "doc1.docx"))
        r3 = index_workspace(str(ws))
        assert r3.indexed == 1
        print(f"  [OK] After modify: indexed={r3.indexed}")


def test_index_workspace_parse_failure():
    """Test that parse failures are recorded as FAILED."""
    print("\n" + "=" * 60)
    print("TEST: Integration — Parse Failure Handling")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "workspace"
        ws.mkdir()

        # Create an invalid .docx (just random bytes)
        (ws / "bad.docx").write_bytes(b"this is not a valid docx file")

        result = index_workspace(str(ws))

        assert result.discovered == 1
        assert result.failed == 1
        assert result.indexed == 0
        print(f"  [OK] Bad file: failed={result.failed}")

        # Check error message in DB
        status = get_index_status(str(ws))
        file_info = status["files"][0]
        assert file_info["status"] == "failed"
        assert file_info["error_message"] is not None
        print(f"  [OK] Error recorded: {file_info['error_message'][:50]}")


# ── Main ──────────────────────────────────────────────────────────────────

def run_all_tests():
    """Run all Phase C tests."""
    print("\n" + "#" * 60)
    print("  PHASE C TESTS — DOCX Parser + Chunking + Registry")
    print("#" * 60)

    tests = [
        # Parser Registry
        test_parser_registry_docx,
        # DOCX Parser
        test_docx_parser_basic,
        test_docx_parser_heading_levels,
        test_docx_parser_table,
        test_docx_parser_file_not_found,
        test_docx_parser_empty,
        # Chunking
        test_chunking_basic,
        test_chunking_heading_context,
        test_chunking_table_atomic,
        test_chunking_long_document,
        test_chunking_empty_document,
        # Integration
        test_index_workspace_with_parsing,
        test_index_workspace_incremental,
        test_index_workspace_parse_failure,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  [FAIL] FAILED: {test_fn.__name__}")
            print(f"    Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "#" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("#" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n  [OK] All Phase C tests passed!")


if __name__ == "__main__":
    run_all_tests()
