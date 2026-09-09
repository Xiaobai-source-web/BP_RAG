"""
演示脚本：扫描指定目录中的 .docx 文件

用法：
    python scripts/scan_demo.py <目录路径>

示例：
    python scripts/scan_demo.py D:/Projects/Huizhou
    python scripts/scan_demo.py ./test_workspace
"""

import sys
import logging
from pathlib import Path

# 把项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from buildplan_knowledge import index_workspace, get_index_status

# 配置日志，输出到终端
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
# 只显示我们自己的日志，屏蔽第三方库
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger("buildplan_knowledge")
logger.setLevel(logging.INFO)


def main():
    # ── 1. 获取目录路径 ────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print("用法: python scripts/scan_demo.py <目录路径>")
        print("示例: python scripts/scan_demo.py D:/Projects/Huizhou")
        sys.exit(1)

    workspace_path = sys.argv[1]
    ws = Path(workspace_path).resolve()

    if not ws.is_dir():
        print(f"错误: 目录不存在 → {ws}")
        sys.exit(1)

    print("=" * 60)
    print(f"  扫描 Workspace: {ws}")
    print("=" * 60)

    # ── 2. 执行索引（Phase B 只做扫描，不做解析） ──────────────────────
    result = index_workspace(str(ws))

    # ── 3. 打印汇总结果 ────────────────────────────────────────────────
    print(f"\n  workspace_id : {result.workspace_id}")
    print(f"  发现文件数   : {result.discovered}")
    print(f"  新索引       : {result.indexed}")
    print(f"  跳过(未变更) : {result.skipped}")
    print(f"  失败         : {result.failed}")

    # ── 4. 打印每个文件的详情 ──────────────────────────────────────────
    if result.files:
        print(f"\n{'─' * 60}")
        print(f"  {'文件路径':<35} {'状态':<8}")
        print(f"{'─' * 60}")
        for f in result.files:
            print(f"  {f.relative_path:<35} {f.status.value:<8}")
        print(f"{'─' * 60}")
    else:
        print("\n  未发现任何 .docx 文件。")
        print("  请确认目录中包含 .docx 文件，且不在被忽略的子目录中。")

    # ── 5. 显示 SQLite 中的完整状态 ────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  SQLite 数据库状态")
    print(f"{'=' * 60}")

    status = get_index_status(str(ws))
    print(f"  workspace_id : {status['workspace_id']}")
    print(f"  DB 文件数    : {status['discovered_files']}")
    print(f"  已索引       : {status['indexed_files']}")
    print(f"  失败         : {status['failed_files']}")
    print(f"  Chunk 总数   : {status['total_chunks']}")

    if status["files"]:
        print(f"\n  数据库记录:")
        for f in status["files"]:
            hash_short = f["file_hash"][:12] + "..." if f["file_hash"] else "N/A"
            print(f"    {f['relative_path']}")
            print(f"      状态: {f['status']}  大小: {f['file_size']} bytes  hash: {hash_short}")

    print(f"\n{'=' * 60}")
    print(f"  .buildplan/ 目录已创建在 workspace 中")
    print(f"  包含: project.db (SQLite) + workspace.json (UUID)")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
