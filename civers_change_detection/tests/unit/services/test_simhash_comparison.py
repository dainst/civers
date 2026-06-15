"""Unit tests for SimHashComparison algorithm.

Tests cover: identical text, minor edits within threshold, major changes,
threshold boundaries, threshold=0 edge case, and changed_token_sample inclusion.
"""

from __future__ import annotations


from change_detection_services.comparison.simhash_comparison import SimHashComparison


def test_simhash_comparison_identical() -> None:
    """Test that identical texts result in distance 0 and similarity 1.0."""
    comparator = SimHashComparison(threshold=3)
    content = "This is a sample document for testing simhash comparison."
    result = comparator.compare(content, content)

    assert result.changed is False
    assert result.similarity_score == 1.0
    assert result.algorithm_name == "simhash"
    assert "changed_token_sample" not in result.details
    assert isinstance(result.details["fingerprint_current"], str)
    assert result.details["fingerprint_current"] == "0xcb0fee2e3a7d5cd4"
    assert result.details["fingerprint_previous"] == "0xcb0fee2e3a7d5cd4"
    assert result.details["hamming_distance"] == 0
    assert result.details["threshold"] == 3


def test_simhash_comparison_minor_change_within_threshold() -> None:
    """Test that minor change within the threshold is not considered a change."""
    # A single word change should keep hamming distance very low (usually <= 3)
    comparator = SimHashComparison(threshold=3)
    current = "This is a sample document for testing simhash comparison."
    previous = "This is a sample document for testing simhash comparisons."
    result = comparator.compare(current, previous)

    # We expect this to be identical or under the threshold of 3
    assert result.details["hamming_distance"] <= 3
    assert result.changed is False
    assert "changed_token_sample" not in result.details


def test_simhash_comparison_major_change() -> None:
    """Test that major change results in changed=True and details populating."""
    comparator = SimHashComparison(threshold=3)
    current = (
        "Python is an interpreted high-level general-purpose programming language."
    )
    previous = "The quick brown fox jumps over the lazy dog."
    result = comparator.compare(current, previous)

    assert result.changed is True
    assert result.similarity_score < 0.9
    assert result.details["hamming_distance"] > 3
    assert "changed_token_sample" in result.details
    assert isinstance(result.details["changed_token_sample"], list)
    assert len(result.details["changed_token_sample"]) <= 10
    assert result.details["changed_token_sample"] == [
        "Python",
        "The",
        "an",
        "brown",
        "dog.",
        "fox",
        "general-purpose",
        "high-level",
        "interpreted",
        "is",
    ]
    assert result.details["fingerprint_current"] == "0xfebaac759aa70a1e"
    assert result.details["fingerprint_previous"] == "0x2c2a1290908a898a"
    assert result.details["threshold"] == 3
    assert result.details["hamming_distance"] == 29


def test_simhash_comparison_threshold_zero() -> None:
    """Test that threshold=0 detects even the smallest change."""
    comparator = SimHashComparison(threshold=0)
    current = "This is a sample document for testing simhash comparison."
    previous = "This is a sample document for testing simhash comparisons."
    result = comparator.compare(current, previous)

    # Since threshold is 0, any distance > 0 must result in changed=True
    assert result.changed is True
    assert "changed_token_sample" in result.details


def test_simhash_comparison_empty_strings() -> None:
    """Test behavior with empty strings."""
    comparator = SimHashComparison(threshold=3)

    # Both empty
    res1 = comparator.compare("", "")
    assert res1.changed is False
    assert res1.similarity_score == 1.0
    assert res1.details["hamming_distance"] == 0

    # One empty
    res2 = comparator.compare("Some content here", "")
    assert res2.changed is True
    assert res2.similarity_score < 0.8
