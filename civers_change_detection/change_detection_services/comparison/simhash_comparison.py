"""Locality-sensitive hashing (SimHash) comparison algorithm.

Computes 64-bit fingerprints of content strings, checks their Hamming
distance against a threshold, and returns similarity metrics and token-level diffs.
"""

from __future__ import annotations

from typing import Any

import simhash

from .comparison_interface import ComparisonAlgorithmInterface, ComparisonResult


class SimHashComparison(ComparisonAlgorithmInterface):
    """Near-duplicate detection algorithm using SimHash.

    Computes a 64-bit fingerprint of each text and compares them using Hamming
    distance. If the Hamming distance is greater than the configured threshold,
    the content is considered changed.
    """

    def __init__(self, threshold: int = 3) -> None:
        """Initialize SimHash comparison.

        Args:
            threshold: Hamming distance threshold (0 to 64). Distances greater
                than this threshold are considered changes. Default is 3.
        """
        self.threshold = threshold

    @property
    def name(self) -> str:
        """Unique name identifier matching the config value."""
        return "simhash"

    def compare(self, current_content: str, previous_content: str) -> ComparisonResult:
        """Compare current content against a previous version using SimHash.

        Args:
            current_content: The newly fetched and extracted text.
            previous_content: The previously stored text.

        Returns:
            A ``ComparisonResult`` with change status, similarity score,
            and SimHash metrics.
        """
        # Handle empty string edge cases to avoid zero division or hashing issues
        if not current_content and not previous_content:
            return ComparisonResult(
                changed=False,
                similarity_score=1.0,
                algorithm_name=self.name,
                details={
                    "hamming_distance": 0,
                    "threshold": self.threshold,
                    "fingerprint_current": "0x0",
                    "fingerprint_previous": "0x0",
                },
            )

        # Compute simhash fingerprints
        sh_curr = simhash.Simhash(current_content)
        sh_prev = simhash.Simhash(previous_content)

        distance = sh_curr.distance(sh_prev)
        changed = distance > self.threshold
        similarity_score = 1.0 - (distance / 64.0)

        details: dict[str, Any] = {
            "hamming_distance": distance,
            "threshold": self.threshold,
            "fingerprint_current": hex(sh_curr.value),
            "fingerprint_previous": hex(sh_prev.value),
        }

        # Include token differences when changes are detected
        if changed:
            # Set difference of whitespace-split words
            tokens_curr = set(current_content.split())
            tokens_prev = set(previous_content.split())
            diff_tokens = tokens_curr.symmetric_difference(tokens_prev)
            details["changed_token_sample"] = sorted(list(diff_tokens))[:10]

        return ComparisonResult(
            changed=changed,
            similarity_score=similarity_score,
            algorithm_name=self.name,
            details=details,
        )
