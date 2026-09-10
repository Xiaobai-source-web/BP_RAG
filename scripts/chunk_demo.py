"""
演示脚本：查看 DOCX 文档的分块结果

用法：
    python scripts/chunk_demo.py <docx文件路径> [--all]

示例：
    python scripts/chunk_demo.py ./test_workspace/扫描测试.docx
    python scripts/chunk_demo.py ./test_workspace/扫描测试.docx --all   # 显示全部 chunk

默认显示前 15 个 chunk，--all 显示全部。
"""

import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from buildplan_knowledge import config
from buildplan_knowledge.parsers import DocxParser
from buildplan_knowledge.chunking import chunk_document
from buildplan_knowledge.schemas import ElementType

# 静默第三方日志
logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

DEFAULT_LIMIT = 15
CHARS_PER_TOKEN = 1.5


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文为主场景：1 token ≈ 1.5 字符）。"""
    return int(len(text) / CHARS_PER_TOKEN)


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/chunk_demo.py <docx文件路径> [--all]")
        sys.exit(1)

    file_path = Path(sys.argv[1]).resolve()
    if not file_path.exists():
        print(f"错误: 文件不存在 -> {file_path}")
        sys.exit(1)

    show_all = "--all" in sys.argv

    # ── 解析 ──────────────────────────────────────────────────────────
    parser = DocxParser()
    parsed = parser.parse(file_path, document_id="demo")
    parsed.relative_path = file_path.name

    # ── 分块 ──────────────────────────────────────────────────────────
    chunks = chunk_document(parsed, workspace_id="demo-ws")

    # ── 标题 ──────────────────────────────────────────────────────────
    print("=" * 80)
    print(f"  文件: {file_path.name}")
    print(f"  解析元素: {len(parsed.elements)}  |  分块数: {len(chunks)}")
    if not show_all:
        print(f"  (显示前 {min(DEFAULT_LIMIT, len(chunks))} 个，加 --all 显示全部)")
    print("=" * 80)

    # ── 逐 Chunk 输出 ─────────────────────────────────────────────────
    display_chunks = chunks if show_all else chunks[:DEFAULT_LIMIT]

    for c in display_chunks:
        hp = " > ".join(c.heading_path) if c.heading_path else "(无)"
        text_preview = c.text[:300].replace("\n", "\\n")
        if len(c.text) > 300:
            text_preview += "..."
        embed_preview = c.embedding_text[:300].replace("\n", "\\n")
        if len(c.embedding_text) > 300:
            embed_preview += "..."

        meta = c.metadata
        meta_str = f"ws={meta.workspace_id[:8]}... doc={meta.document_id[:8]}... file={meta.file_name}"

        print(f"\n{'─' * 80}")
        print(f"  chunk_index : {c.chunk_index}")
        print(f"  chunk_id    : {c.chunk_id}")
        print(f"  heading_path: {hp}")
        print(f"  字符数      : {len(c.text)}")
        print(f"  估算 tokens : {estimate_tokens(c.text)}")
        print(f"  metadata    : {meta_str}")
        print(f"  text        : {text_preview}")
        print(f"  embedding   : {embed_preview}")

    if not show_all and len(chunks) > DEFAULT_LIMIT:
        print(f"\n  ... 还有 {len(chunks) - DEFAULT_LIMIT} 个 chunk 未显示，加 --all 查看全部")

    # ── Overlap 检查 ──────────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  Overlap 检查")
    print(f"{'=' * 80}")

    overlap_found = 0
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1].text[-200:]
        curr_head = chunks[i].text[:200]
        # 检查前一个 chunk 的尾部文本是否出现在当前 chunk 中
        # 取 prev_tail 的后半段作为检测片段
        check_len = min(80, len(prev_tail))
        check_segment = prev_tail[-check_len:]
        if check_segment and check_segment in chunks[i].text:
            overlap_found += 1
            if overlap_found <= 3:  # 只显示前 3 个
                print(f"\n  chunk[{i-1}] -> chunk[{i}]: 检测到 overlap")
                print(f"    重叠片段: ...{check_segment[:60]}...")

    if overlap_found == 0:
        sizes = [len(c.text) for c in chunks]
        max_size = max(sizes) if sizes else 0
        if max_size < config.CHUNK_TARGET_CHARS:
            print(f"\n  所有 chunk 均未超过目标大小 ({config.CHUNK_TARGET_CHARS} 字符)，无需拆分，无 overlap 是正确行为。")
        else:
            print(f"\n  [注意] 存在超大 chunk ({max_size} 字符) 但未检测到 overlap，请检查分块逻辑。")
    else:
        print(f"\n  共检测到 {overlap_found} 处 overlap")

    # ── 汇总统计 ──────────────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  分块统计")
    print(f"{'=' * 80}")

    sizes = [len(c.text) for c in chunks]
    if sizes:
        print(f"  总 chunk 数  : {len(chunks)}")
        print(f"  最小字符数   : {min(sizes)}")
        print(f"  最大字符数   : {max(sizes)}")
        print(f"  平均字符数   : {sum(sizes) / len(sizes):.0f}")
        print(f"  目标 chunk   : 900 字符")
        print(f"  overlap 设定 : 150 字符")

        # 含 heading_path 的 chunk 数
        with_hp = sum(1 for c in chunks if c.heading_path)
        print(f"  有 heading   : {with_hp}/{len(chunks)}")

        # 含表格的 chunk
        table_chunks = sum(1 for c in chunks if "|" in c.text and c.text.count("|") >= 4)
        print(f"  表格 chunk   : {table_chunks}")

    print(f"\n{'=' * 80}")
    print("  完成")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
