"""
BuildPlan Knowledge Tool — Parsers

Document parsers for various file formats.
V0.1: DOCX only.
"""

from .base import BaseParser
from .docx import DocxParser
from .registry import get_parser, supported_extensions

__all__ = [
    "BaseParser",
    "DocxParser",
    "get_parser",
    "supported_extensions",
]
