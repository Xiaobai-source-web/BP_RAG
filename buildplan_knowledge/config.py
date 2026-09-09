"""
BuildPlan Knowledge Tool — Unified Configuration

All tuneable parameters live here. No magic numbers in business code.
"""

from pathlib import Path

# ── Chunking (for Phase D, declared here for centralisation) ──────────────
CHUNK_TARGET_TOKENS: int = 600
CHUNK_OVERLAP_TOKENS: int = 100
# V0.1 uses character-based approximation: 1 token ≈ 1.5 Chinese characters
CHARS_PER_TOKEN: float = 1.5

CHUNK_TARGET_CHARS: int = int(CHUNK_TARGET_TOKENS * CHARS_PER_TOKEN)   # ~900
CHUNK_OVERLAP_CHARS: int = int(CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN)  # ~150

# ── Embedding (for Phase E, declared here for centralisation) ─────────────
EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIMENSION: int = 512
EMBEDDING_BATCH_SIZE: int = 32

# ── Retrieval ─────────────────────────────────────────────────────────────
TOP_K_DEFAULT: int = 5

# ── SQLite ────────────────────────────────────────────────────────────────
BUILDPLAN_DIR_NAME: str = ".buildplan"
PROJECT_DB_NAME: str = "project.db"
WORKSPACE_META_NAME: str = "workspace.json"

def get_buildplan_dir(workspace_path: str | Path) -> Path:
    """Return the .buildplan/ directory inside a workspace."""
    return Path(workspace_path) / BUILDPLAN_DIR_NAME

def get_db_path(workspace_path: str | Path) -> Path:
    """Return the project.db path inside a workspace's .buildplan/."""
    return get_buildplan_dir(workspace_path) / PROJECT_DB_NAME

def get_workspace_meta_path(workspace_path: str | Path) -> Path:
    """Return the workspace.json path inside .buildplan/."""
    return get_buildplan_dir(workspace_path) / WORKSPACE_META_NAME

# ── Workspace Scanner ─────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS: set[str] = {
    ".docx",
    # Future: ".pdf", ".xlsx", ".md", ".txt"
}

IGNORED_DIRS: set[str] = {
    ".buildplan",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
}

# ── Parser version ────────────────────────────────────────────────────────
PARSER_VERSION: str = "v0.1"
