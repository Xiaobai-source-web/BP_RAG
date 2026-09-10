"""
BuildPlan Knowledge Tool — Base Parser

Abstract interface for all document parsers.
Each parser converts a file into a ParsedDocument.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..schemas import ParsedDocument


class BaseParser(ABC):
    """
    Abstract base class for document parsers.

    Subclasses must implement parse() to convert a file into a ParsedDocument.
    """

    @abstractmethod
    def parse(self, file_path: str | Path, document_id: str) -> ParsedDocument:
        """
        Parse a document file and return structured elements.

        Args:
            file_path: Absolute or relative path to the document.
            document_id: Unique identifier for this document.

        Returns:
            ParsedDocument with elements (heading, paragraph, table).
        """
        ...
