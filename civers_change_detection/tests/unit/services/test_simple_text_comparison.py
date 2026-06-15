"""Unit tests for SimpleTextComparison algorithm.

Tests cover: identical text, whitespace normalization, completely different
content, partial changes with similarity scoring, empty strings, and
diff_snippet inclusion.
"""

from __future__ import annotations


from change_detection_services.comparison.simple_text_comparison import (
    SimpleTextComparison,
)


def test_simple_text_comparison_identical() -> None:
    """Test that identical texts result in no change and similarity 1.0."""
    comparator = SimpleTextComparison()
    content = "Hello, world! This is a test."
    result = comparator.compare(content, content)

    assert result.changed is False
    assert result.similarity_score == 1.0
    assert result.algorithm_name == "simple_text"
    assert "diff_snippet" not in result.details
    assert result.details["normalized_length_current"] == len(content)
    assert result.details["normalized_length_previous"] == len(content)


def test_simple_text_comparison_whitespace_normalization() -> None:
    """Test that formatting/whitespace differences are normalized and ignored."""
    comparator = SimpleTextComparison()
    current = "  Hello, \n world!   This   is a test.  "
    previous = "Hello, world! This is a test."
    result = comparator.compare(current, previous)

    assert result.changed is False
    assert result.similarity_score == 1.0
    assert "diff_snippet" not in result.details
    assert result.details["normalized_length_current"] == len(previous)


def test_simple_text_comparison_completely_different() -> None:
    """Test that completely different contents result in changed=True and low similarity."""
    comparator = SimpleTextComparison()
    current = "Python is an interpreted, high-level programming language."
    previous = "The quick brown fox jumps over the lazy dog."
    result = comparator.compare(current, previous)

    assert result.changed is True
    assert result.similarity_score < 0.2  # Very low similarity
    assert "diff_snippet" in result.details
    assert isinstance(result.details["diff_snippet"], str)


def test_simple_text_comparison_partial_change() -> None:
    """Test that a partial change results in changed=True and a matching similarity score."""
    comparator = SimpleTextComparison()
    current = "Welcome to the DAInst change detection service. Version 1.0."
    previous = "Welcome to the DAInst change detection service. Version 0.9."
    result = comparator.compare(current, previous)

    assert result.changed is True
    # Most characters are identical, similarity should be high but less than 1.0
    assert 0.8 < result.similarity_score < 1.0
    assert "diff_snippet" in result.details
    assert "Version 1.0" in result.details["diff_snippet"]
    assert "Version 0.9" in result.details["diff_snippet"]


def test_simple_text_comparison_empty_strings() -> None:
    """Test behavior with empty strings."""
    comparator = SimpleTextComparison()

    # Both empty
    res1 = comparator.compare("", "")
    assert res1.changed is False
    assert res1.similarity_score == 1.0

    # Current empty, previous not
    res2 = comparator.compare("", "Some content")
    assert res2.changed is True
    assert res2.similarity_score == 0.0

    # Previous empty, current not
    res3 = comparator.compare("Some content", "")
    assert res3.changed is True
    assert res3.similarity_score == 0.0


def test_simple_text_comparison_word_level() -> None:
    """Test that similarity scoring operates at the word level, not character level."""
    comparator = SimpleTextComparison()
    # A single word mismatch will result in 0.0 similarity at the word level,
    # whereas at the character level, "cat" and "cats" would have high similarity.
    result = comparator.compare("cat", "cats")
    assert result.changed is True
    assert result.similarity_score == 0.0
