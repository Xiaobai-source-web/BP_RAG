# BuildPlan Knowledge Tool V0.1

本地优先（Local-first）的 Workspace 知识索引与检索工具，未来作为 BuildPlan Main Agent 的 Tool 使用。

## 项目目标

将本地 Workspace 中的文档通过 **扫描 → 解析 → 分块 → 向量化 → 索引** 流程，建立可语义检索的知识库。本模块只返回 Evidence，不负责最终自然语言回答。

```
Workspace → 文件扫描 → 文件解析 → 结构化 Chunk → Embedding → 本地向量索引 → Semantic Retrieval → Evidence
```

Main Agent 只需调用三个 API：

```python
index_workspace(workspace_path)      # 索引工作区
search_knowledge(workspace_path, q)  # 语义检索
get_index_status(workspace_path)     # 查看状态
```

## 当前开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase A | 环境检查与技术选型 | ✅ 完成 |
| Phase B | SQLite + Workspace Scanner + Public API 骨架 | ✅ 完成 |
| Phase C | DOCX Parser（结构化解析） | ⬜ 待实现 |
| Phase D | Structure-aware Chunker | ⬜ 待实现 |
| Phase E | Embedding + Vector Store + 索引 | ⬜ 待实现 |
| Phase F | search_knowledge() 完整实现 | ⬜ 待实现 |
| Phase G | 固定 Testset + Recall 评估 | ⬜ 待实现 |
| Phase H | 增量索引完整测试 | ⬜ 待实现 |
| Phase I | 大型 DOCX 压力测试 | ⬜ 待实现 |
| Phase J | 可选 LLM Demo | ⬜ 待实现 |

## 目录结构

```
RAG/
├── buildplan_knowledge/           # 核心模块
│   ├── __init__.py                # Public API 导出
│   ├── api.py                     # 三个公共入口函数
│   ├── config.py                  # 统一配置（chunk size、embedding 等）
│   ├── schemas.py                 # 数据结构定义
│   ├── database.py                # SQLite 数据库管理
│   ├── workspace.py               # Workspace 文件扫描
│   ├── parsers/                   # 文档解析器（Phase C）
│   │   └── __init__.py
│   ├── chunking/                  # 分块器（Phase D）
│   │   └── __init__.py
│   ├── embeddings/                # Embedding 层（Phase E）
│   │   └── __init__.py
│   ├── vectorstores/              # 向量存储层（Phase E）
│   │   └── __init__.py
│   └── retrieval/                 # 检索层（Phase F）
│       └── __init__.py
├── scripts/
│   └── scan_demo.py               # 扫描演示脚本
├── test_workspace/                # 测试工作区（含 .docx 示例）
├── 测试/                          # 测试用 DOCX 文件
├── 编程指引.md                     # 完整技术规范
├── requirements.txt
├── .gitignore
└── README.md
```

## 快速开始

### 环境要求

- Python 3.12+
- Windows（V0.1 目标平台）

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd RAG

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 运行扫描演示

```bash
python scripts/scan_demo.py ./test_workspace
```

输出示例：

```
============================================================
  扫描 Workspace: D:\Desktop\RAG\test_workspace
============================================================

  workspace_id : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  发现文件数   : 1
  新索引       : 1
  跳过(未变更) : 0
  失败         : 0
```

## Public API

### `index_workspace(workspace_path)`

扫描 Workspace，发现支持的文件，更新 SQLite 索引。

- 新文件 → 解析、分块、索引
- 已修改文件（hash 变化）→ 删除旧索引，重新索引
- 已删除文件 → 清理 SQLite 记录和向量
- 未变更文件 → 跳过

### `search_knowledge(workspace_path, query, scope, top_k, filters)`

语义检索，返回 Top-K Evidence。

- `scope`: V0.1 仅支持 `"workspace"`
- `top_k`: 默认 5
- 返回 `RetrievalResult`，包含 chunk text、score、source 信息

### `get_index_status(workspace_path)`

返回索引状态：文件数、已索引数、失败数、Chunk 总数、每个文件详情。

## 技术选型

| 组件 | 选择 | 说明 |
|------|------|------|
| 文档解析 | python-docx | 识别 Heading / Paragraph / Table |
| 分块策略 | Structure-aware + Size-based Split | 目标 ~600 tokens，重叠 ~100 tokens |
| Embedding | BAAI/bge-small-zh-v1.5 | 本地运行，中英文支持，512 维 |
| 向量存储 | 本地持久化 | 不依赖外部服务器 |
| 元数据存储 | SQLite | 文件台账 + 索引状态 |
| 增量索引 | SHA-256 hash 比对 | 仅重新索引变更文件 |

## 配置

所有可调参数集中在 `buildplan_knowledge/config.py`：

```python
CHUNK_TARGET_TOKENS = 600      # 分块目标 token 数
CHUNK_OVERLAP_TOKENS = 100     # 分块重叠 token 数
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIMENSION = 512
TOP_K_DEFAULT = 5
SUPPORTED_EXTENSIONS = {".docx"}  # 未来扩展: .pdf, .xlsx, .md
```

## 安全与隐私

- **完全本地运行**：不上传用户文件，不调用外部服务
- **不修改原文件**：只读取，不写入用户文档
- **数据隔离**：`.buildplan/` 目录存储所有索引数据
- **Git 安全**：`.env`、数据库、向量索引、模型缓存均已 gitignore

## V0.1 完成标准

- [ ] DOCX Workspace 扫描
- [ ] DOCX 结构解析
- [ ] Structure-aware Chunking
- [ ] Local Embedding
- [ ] Local Persistent Vector Store
- [ ] SQLite 文件台账
- [ ] Incremental Indexing
- [ ] search_knowledge()
- [ ] Top-K Evidence + Metadata
- [ ] 固定 Testset + Recall@1/3/5
- [ ] Agent-independent Public API
- [ ] 完全 Local-first

## 参考

完整技术规范见 [编程指引.md](编程指引.md)。
