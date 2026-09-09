"""
BuildPlan Knowledge Tool V0.1

Local-first Workspace Knowledge Indexing & Retrieval Tool.
Designed to be used as a Tool by BuildPlan Main Agent.
"""

from .api import get_index_status, index_workspace, search_knowledge

__all__ = [
    "index_workspace",
    "search_knowledge",
    "get_index_status",
]
