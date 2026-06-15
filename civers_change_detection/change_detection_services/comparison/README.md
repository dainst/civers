# Change Detection — Content Comparison Layer

This module provides pluggable text comparison strategies for determining whether extracted web page content has changed between fetches.

---

## Architecture Overview

All comparison algorithms implement the `ComparisonAlgorithmInterface` and are dynamically resolved by name from the domain configurations.

```
                  +--------------------------------+
                  |  ComparisonAlgorithmInterface  |
                  +--------------------------------+
                                  ^
                                  |
            +---------------------+---------------------+
            |                                           |
+-----------------------+                   +-----------------------+
| SimpleTextComparison  |                   |   SimHashComparison   |
+-----------------------+                   +-----------------------+
- Whitespace normalized                     - Locality-sensitive LSH
- Character difflib ratio                   - Hamming distance threshold
- Sentence-level unified diff               - Token set difference list
```

---

## Key Interfaces

### `ComparisonAlgorithmInterface`
Defines the contract for content comparison algorithms.
* `name`: Property returning the unique string identifier (e.g., `"simhash"` or `"simple_text"`).
* `compare(current_content: str, previous_content: str) -> ComparisonResult`: Receives the newly extracted page text and the previously stored text, returning a structured comparison result.

### `ComparisonResult`
The unified dataclass returned by all comparison algorithms.
* `changed` (`bool`): Evaluates to `True` if differences exceed the configured threshold.
* `similarity_score` (`float`): Normalized similarity value between `0.0` (completely different) and `1.0` (identical).
* `algorithm_name` (`str`): The identifier of the algorithm that performed the comparison.
* `details` (`dict[str, Any]`): Pluggable, algorithm-specific metadata.

---

## Comparison Algorithms

### 1. Simple Text Comparison (`"simple_text"`)
A deterministic comparison strategy designed for exact text equivalence.
* **Normalization**: All runs of whitespace (spaces, tabs, newlines) are collapsed into single spaces, and leading/trailing whitespace is stripped.
* **Equality**: `changed` is `True` if the normalized strings are not identical.
* **Similarity Score**: Calculated using `difflib.SequenceMatcher` ratio representing the proportion of matching characters.
* **Details**:
  - `normalized_length_current` / `normalized_length_previous`: Character lengths.
  - `diff_snippet`: A lightweight, sentence-level unified diff snippet showing exactly what added/removed strings triggered the change. Only populated when `changed=True` to minimize storage consumption.

### 2. SimHash LSH Comparison (`"simhash"`)
Locality-sensitive hashing (LSH) near-duplicate comparison strategy. Useful for ignoring minor updates (e.g., counters, dynamic timestamps) while detecting major structural text updates.
* **Normalization**: Uses the default `simhash` package tokenization.
* **Hamming Distance**: Calculates the number of differing bit positions between the two 64-bit fingerprints (range: `[0, 64]`).
* **Threshold**: If the Hamming distance is strictly greater than the configured `simhash_threshold` (default: `3`), `changed` is set to `True`.
* **Similarity Score**: Normalized linearly as `1.0 - (hamming_distance / 64.0)`.
* **Details**:
  - `hamming_distance` / `threshold`: Integer metrics.
  - `fingerprint_current` / `fingerprint_previous`: Hex representations of the SimHash values.
  - `changed_token_sample`: A list of up to 10 whitespace-split words that differ between current and previous versions (computed via O(n) set symmetric difference).

---

## Dynamic Lookup & Extension

Algorithms are resolved dynamically at runtime using the `get_comparison_algorithm(name, **kwargs)` factory function in `__init__.py`.

To add a new comparison algorithm:
1. Create a new module under `change_detection_services/comparison/`.
2. Implement `ComparisonAlgorithmInterface`.
3. Register the new class mapping inside `get_comparison_algorithm()` in `change_detection_services/comparison/__init__.py`.
