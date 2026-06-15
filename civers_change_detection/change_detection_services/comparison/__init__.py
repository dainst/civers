"""Comparison algorithms for change detection.

Provides pluggable content comparison strategies. Each algorithm
implements ``ComparisonAlgorithmInterface`` and is resolved by name
via ``get_comparison_algorithm()``.

Available algorithms:
    - ``simple_text``: Normalized text equality + difflib similarity ratio.
    - ``simhash``: Locality-sensitive hashing with Hamming distance threshold.
"""

from __future__ import annotations

from .comparison_interface import ComparisonAlgorithmInterface, ComparisonResult

__all__ = [
    "ComparisonAlgorithmInterface",
    "ComparisonResult",
    "get_comparison_algorithm",
]


def get_comparison_algorithm(
    name: str, **kwargs: object
) -> ComparisonAlgorithmInterface:
    """Resolve a comparison algorithm by its config name.

    Args:
        name: Algorithm identifier (must match a registered algorithm's
            ``name`` property, e.g., ``"simhash"`` or ``"simple_text"``).
        **kwargs: Algorithm-specific constructor arguments
            (e.g., ``threshold`` for simhash).

    Returns:
        An instance of the requested comparison algorithm.

    Raises:
        ValueError: If the name does not match any registered algorithm.
    """
    # Lazy imports to avoid circular dependencies and allow
    # each algorithm module to import the interface freely.
    from .simple_text_comparison import SimpleTextComparison
    from .simhash_comparison import SimHashComparison

    registry: dict[str, type[ComparisonAlgorithmInterface]] = {
        "simple_text": SimpleTextComparison,
        "simhash": SimHashComparison,
    }

    cls = registry.get(name)
    if cls is None:
        available = ", ".join(sorted(registry.keys()))
        raise ValueError(
            f"Unknown comparison algorithm: {name!r}. Available: {available}"
        )
    return cls(**kwargs)  # type: ignore[arg-type]
