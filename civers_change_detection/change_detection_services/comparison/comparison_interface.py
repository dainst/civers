"""Comparison algorithm interface and result type.

Defines the contract for content comparison algorithms used by the
change detection service. Each algorithm compares two text strings
and produces a ``ComparisonResult``.

Implementations are registered by name and resolved dynamically from
the ``comparison_algorithm`` config field via ``get_comparison_algorithm()``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComparisonResult:
    """Result of comparing two content versions.

    Attributes:
        changed: Whether the content has changed beyond the configured threshold.
        similarity_score: Normalized similarity between 0.0 (completely different)
            and 1.0 (identical). Interpretation depends on the algorithm.
        algorithm_name: Name identifier of the comparison algorithm that produced
            this result (e.g., ``"simhash"``, ``"simple_text"``).
        details: Algorithm-specific metadata (e.g., hamming distance, diff ratio).
    """

    changed: bool
    similarity_score: float
    algorithm_name: str
    details: dict[str, Any] = field(default_factory=dict)


class ComparisonAlgorithmInterface(ABC):
    """Contract for content comparison algorithms.

    Each algorithm compares two text strings and produces a
    ``ComparisonResult``. Implementations are registered by name
    and resolved dynamically from config.

    To add a new algorithm:
        1. Create a new module in this package.
        2. Subclass ``ComparisonAlgorithmInterface``.
        3. Implement ``name`` and ``compare()``.
        4. Register the class in ``get_comparison_algorithm()``
           in ``__init__.py``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier matching the config value (e.g., ``"simhash"``)."""

    @abstractmethod
    def compare(self, current_content: str, previous_content: str) -> ComparisonResult:
        """Compare current content against a previous version.

        Args:
            current_content: The newly fetched and extracted text.
            previous_content: The previously stored text.

        Returns:
            A ``ComparisonResult`` with change status, similarity score,
            and algorithm-specific details.
        """
