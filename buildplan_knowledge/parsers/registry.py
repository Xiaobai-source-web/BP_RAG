"""
BuildPlan Knowledge Tool — Parser Registry

Maps file extensions to their corresponding parser instances.
Centralizes parser lookup so callers don't need to know about individual parsers.
"""

from __future__ import annotations

from .base import BaseParser
from .docx import DocxParser

# Singleton instances — parsers are stateless, safe to reuse
_DOCX_PARSER = DocxParser()

_PARSER_MAP: dict[str, BaseParser] = {
    ".docx": _DOCX_PARSER,
}


def get_parser(file_extension: str) -> BaseParser | None:
    """
    Return the parser for a given file extension, or None if unsupported.

    Args:
        file_extension: File extension including the dot (e.g. ".docx").

    Returns:
        BaseParser instance, or None.
    """
    return _PARSER_MAP.get(file_extension.lower())


def supported_extensions() -> set[str]:
    """Return the set of file extensions with registered parsers."""
    return set(_PARSER_MAP.keys())
