"""Deterministic text comparison algorithm.

Normalizes whitespace, checks for exact equality, and computes a similarity
ratio. Includes a lightweight diff snippet when changes are detected.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from .comparison_interface import ComparisonAlgorithmInterface, ComparisonResult


class SimpleTextComparison(ComparisonAlgorithmInterface):
    """Deterministic text comparison algorithm.

    Whitespace is normalized by collapsing all runs of whitespace into single
    spaces and stripping leading/trailing whitespace. Similarity is calculated
    using ``difflib.SequenceMatcher`` on the word tokens of the normalized strings.
    """

    @property
    def name(self) -> str:
        """Unique name identifier matching the config value."""
        return "simple_text"

    def compare(self, current_content: str, previous_content: str) -> ComparisonResult:
        """Compare current content against a previous version.

        Args:
            current_content: The newly fetched and extracted text.
            previous_content: The previously stored text.

        Returns:
            A ``ComparisonResult`` with change status, similarity score,
            and algorithm-specific details.
        """
        # Whitespace normalization: collapse runs of whitespace into single spaces
        normalized_current = " ".join(current_content.split())
        normalized_previous = " ".join(previous_content.split())

        changed = normalized_current != normalized_previous

        # Calculate similarity score at word/token level
        curr_words = normalized_current.split()
        prev_words = normalized_previous.split()

        if not curr_words and not prev_words:
            similarity_score = 1.0
        else:
            similarity_score = difflib.SequenceMatcher(
                None, curr_words, prev_words
            ).ratio()

        details: dict[str, Any] = {
            "normalized_length_current": len(normalized_current),
            "normalized_length_previous": len(normalized_previous),
        }

        # Generate a lightweight diff snippet when changed
        if changed:
            # Split into sentence-level chunks for a readable unified diff
            curr_sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", normalized_current)
                if s.strip()
            ]
            prev_sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", normalized_previous)
                if s.strip()
            ]

            diff_generator = difflib.unified_diff(
                prev_sentences,
                curr_sentences,
                fromfile="previous",
                tofile="current",
                lineterm="",
            )

            # Limit the diff output to avoid storing huge amounts of data
            # First 50 lines of diff, with each line truncated to 200 characters
            diff_lines = list(diff_generator)
            truncated_lines = [line[:200] for line in diff_lines[:50]]
            details["diff_snippet"] = "\n".join(truncated_lines)

        return ComparisonResult(
            changed=changed,
            similarity_score=similarity_score,
            algorithm_name=self.name,
            details=details,
        )
