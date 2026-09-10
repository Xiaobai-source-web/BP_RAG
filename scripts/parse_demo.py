"""
演示脚本：解析 DOCX 文件，输出结构化元素

用法：
    python scripts/parse_demo.py <docx文件路径>

示例：
    python scripts/parse_demo.py ./test_workspace/扫描测试.docx
"""

import sys
import logging
from pathlib import Path

# 把项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from buildplan_knowledge.parsers import DocxParser
from buildplan_knowledge.schemas import ElementType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger("buildplan_knowledge")
logger.setLevel(logging.INFO)


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/parse_demo.py <docx文件路径>")
        print("示例: python scripts/parse_demo.py ./test_workspace/扫描测试.docx")
        sys.exit(1)

    file_path = Path(sys.argv[1]).resolve()
    if not file_path.exists():
        print(f"错误: 文件不存在 → {file_path}")
        sys.exit(1)

    if not file_path.suffix.lower() == ".docx":
        print(f"错误: 不是 .docx 文件 → {file_path}")
        sys.exit(1)

    print("=" * 70)
    print(f"  解析 DOCX: {file_path.name}")
    print("=" * 70)

    # ── 解析 ──────────────────────────────────────────────────────────
    parser = DocxParser()
    doc = parser.parse(file_path, document_id="demo-001")

    # ── 汇总 ──────────────────────────────────────────────────────────
    headings = [e for e in doc.elements if e.element_type == ElementType.HEADING]
    paragraphs = [e for e in doc.elements if e.element_type == ElementType.PARAGRAPH]
    tables = [e for e in doc.elements if e.element_type == ElementType.TABLE]

    print(f"\n  总元素数: {len(doc.elements)}")
    print(f"  Heading : {len(headings)}")
    print(f"  Paragraph: {len(paragraphs)}")
    print(f"  Table    : {len(tables)}")

    # ── 逐元素输出 ────────────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print(f"  {'#':<4} {'类型':<12} {'Level':<6} {'heading_path':<30} {'文本预览'}")
    print(f"{'─' * 70}")

    for i, elem in enumerate(doc.elements):
        etype = elem.element_type.value
        level = str(elem.level) if elem.level is not None else "-"
        hp = " > ".join(elem.heading_path) if elem.heading_path else "-"
        text = elem.text[:60].replace("\n", "\\n") if elem.text else "(空)"

        # 表格特殊处理
        if elem.element_type == ElementType.TABLE:
            rows = elem.metadata.get("rows", "?")
            cols = elem.metadata.get("columns", "?")
            text = f"[{rows}行 x {cols}列] {text}"

        print(f"  {i:<4} {etype:<12} {level:<6} {hp:<30} {text}")

    print(f"{'─' * 70}")

    # ── Heading 结构树 ────────────────────────────────────────────────
    if headings:
        print(f"\n  Heading 结构:")
        for h in headings:
            indent = "  " * (h.level - 1) if h.level else ""
            print(f"    {indent}{'#' * (h.level or 1)} {h.text}")

    print(f"\n{'=' * 70}")
    print(f"  解析完成")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
