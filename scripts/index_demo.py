"""
演示脚本：完整索引流程（扫描 → 解析 → 分块）

用法：
    python scripts/index_demo.py <工作区目录>

示例：
    python scripts/index_demo.py ./test_workspace
"""

import sys
import logging
from pathlib import Path

# 把项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from buildplan_knowledge.api import index_workspace, get_index_status
from buildplan_knowledge.parsers import get_parser
from buildplan_knowledge.chunking import chunk_document

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
        print("用法: python scripts/index_demo.py <工作区目录>")
        print("示例: python scripts/index_demo.py ./test_workspace")
        sys.exit(1)

    ws_path = Path(sys.argv[1]).resolve()
    if not ws_path.is_dir():
        print(f"错误: 目录不存在 → {ws_path}")
        sys.exit(1)

    print("=" * 70)
    print(f"  索引工作区: {ws_path}")
    print("=" * 70)

    # ── Step 1: 索引 ────────────────────────────────────────────────────
    print("\n[1/3] 扫描 + 解析 + 分块...")
    result = index_workspace(str(ws_path))

    print(f"\n  发现文件: {result.discovered}")
    print(f"  已索引  : {result.indexed}")
    print(f"  已跳过  : {result.skipped}")
    print(f"  失败    : {result.failed}")
    print(f"  总分块数: {result.total_chunks}")

    # ── Step 2: 文件详情 ────────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print(f"  {'文件':<30} {'状态':<10} {'分块数':<8} {'错误'}")
    print(f"{'─' * 70}")
    for f in result.files:
        err = f.error_message or ""
        print(f"  {f.file_name:<30} {f.status.value:<10} {f.chunk_count:<8} {err[:30]}")
    print(f"{'─' * 70}")

    # ── Step 3: 展示分块详情 ────────────────────────────────────────────
    print("\n[2/3] 分块详情预览...")
    _show_chunk_preview(ws_path)

    # ── Step 4: 索引状态 ────────────────────────────────────────────────
    print("\n[3/3] 索引状态查询...")
    status = get_index_status(str(ws_path))
    print(f"  workspace_id : {status['workspace_id']}")
    print(f"  总文件数     : {status['discovered_files']}")
    print(f"  已索引文件   : {status['indexed_files']}")
    print(f"  总分块数     : {status['total_chunks']}")

    print(f"\n{'=' * 70}")
    print(f"  索引完成")
    print(f"{'=' * 70}\n")


def _show_chunk_preview(ws_path: Path):
    """Parse and chunk each file, showing chunk details."""
    from buildplan_knowledge.database import DatabaseManager

    with DatabaseManager(ws_path) as db:
        files = db.get_indexed_files()
        ws_id = db.get_or_create_workspace_id()

    for file_record in files:
        abs_path = ws_path / file_record["relative_path"]
        if not abs_path.exists():
            continue

        parser = get_parser(file_record["file_type"])
        if parser is None:
            continue

        parsed = parser.parse(abs_path, file_record["document_id"])
        parsed.relative_path = file_record["relative_path"]

        chunks = chunk_document(parsed, workspace_id=ws_id)

        print(f"\n  >> {file_record['file_name']} -> {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            text_preview = chunk.text[:80].replace("\n", "\\n")
            hp = " > ".join(chunk.heading_path) if chunk.heading_path else "-"
            print(f"     [{i}] heading: {hp}")
            print(f"         text: {text_preview}...")


if __name__ == "__main__":
    main()
