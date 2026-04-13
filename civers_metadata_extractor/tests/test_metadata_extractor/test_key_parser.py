"""
Unit Tests for KeyParser

Tests the parsing of flattened key patterns with array notation and wildcards.
"""

import pytest

from metadata_extractors.mappers.key_parser import KeyParseError, KeyParser, PathSegment


class TestPathSegment:
    """Test PathSegment dataclass"""

    def test_simple_segment(self):
        """Test creating a simple non-array segment"""
        seg = PathSegment(name="title", index=None, is_array=False)
        assert seg.name == "title"
        assert seg.index is None
        assert seg.is_array is False

    def test_array_segment_with_index(self):
        """Test creating an array segment with numeric index"""
        seg = PathSegment(name="author", index=0, is_array=True)
        assert seg.name == "author"
        assert seg.index == 0
        assert seg.is_array is True

    def test_array_segment_with_wildcard(self):
        """Test creating an array segment with wildcard"""
        seg = PathSegment(name="tags", index="*", is_array=True)
        assert seg.name == "tags"
        assert seg.index == "*"
        assert seg.is_array is True

    def test_array_segment_with_class_name(self):
        """Test array segment with class name type hint"""
        seg = PathSegment(name="Creator", index="Person", is_array=True)
        assert seg.name == "Creator"
        assert seg.index == "Person"
        assert seg.is_array is True

    def test_validation_empty_name(self):
        """Test that empty names are rejected"""
        with pytest.raises(ValueError, match="name cannot be empty"):
            PathSegment(name="", index=None, is_array=False)

    def test_validation_array_without_index(self):
        """Test that array segments require an index"""
        with pytest.raises(ValueError, match="Array segment must have an index"):
            PathSegment(name="items", index=None, is_array=True)

    def test_validation_non_array_with_index(self):
        """Test that non-array segments cannot have an index"""
        with pytest.raises(ValueError, match="Non-array segment cannot have an index"):
            PathSegment(name="title", index=0, is_array=False)

    def test_validation_negative_index(self):
        """Test that negative indices are rejected"""
        with pytest.raises(ValueError, match="Array index must be non-negative"):
            PathSegment(name="items", index=-1, is_array=True)


class TestKeyParserBasics:
    """Test basic KeyParser functionality"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_parse_simple_key(self):
        """Test parsing a simple key without arrays"""
        segments = self.parser.parse("title")
        assert len(segments) == 1
        assert segments[0] == PathSegment("title", None, False)

    def test_parse_nested_key(self):
        """Test parsing nested keys"""
        segments = self.parser.parse("book.chapter.title")
        assert len(segments) == 3
        assert segments[0] == PathSegment("book", None, False)
        assert segments[1] == PathSegment("chapter", None, False)
        assert segments[2] == PathSegment("title", None, False)

    def test_parse_array_with_index(self):
        """Test parsing array notation with numeric index"""
        segments = self.parser.parse("author[0]")
        assert len(segments) == 1
        assert segments[0] == PathSegment("author", 0, True)

    def test_parse_array_with_wildcard(self):
        """Test parsing array notation with wildcard"""
        segments = self.parser.parse("tags[*]")
        assert len(segments) == 1
        assert segments[0] == PathSegment("tags", "*", True)

    def test_parse_complex_path(self):
        """Test parsing complex nested path with arrays"""
        segments = self.parser.parse("author[0].identifier[*].value")
        assert len(segments) == 3
        assert segments[0] == PathSegment("author", 0, True)
        assert segments[1] == PathSegment("identifier", "*", True)
        assert segments[2] == PathSegment("value", None, False)

    def test_parse_field_with_special_chars(self):
        """Test parsing fields with @ and underscores"""
        segments = self.parser.parse("@context")
        assert segments[0].name == "@context"

        segments = self.parser.parse("name_identifier")
        assert segments[0].name == "name_identifier"

    def test_parse_empty_key_raises_error(self):
        """Test that empty keys raise error"""
        with pytest.raises(KeyParseError, match="Key cannot be empty"):
            self.parser.parse("")

    def test_parse_whitespace_key_raises_error(self):
        """Test that whitespace-only keys raise error"""
        with pytest.raises(KeyParseError, match="Key cannot be empty"):
            self.parser.parse("   ")

    def test_parse_unmatched_bracket_raises_error(self):
        """Test that unmatched brackets raise error"""
        with pytest.raises(KeyParseError, match="Unmatched"):
            self.parser.parse("author[0")

        with pytest.raises(KeyParseError, match="Unmatched"):
            self.parser.parse("author0]")


class TestKeyParserMatching:
    """Test pattern matching functionality"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_matches_pattern_exact(self):
        """Test exact pattern matching"""
        assert self.parser.matches_pattern("title", "title")
        assert self.parser.matches_pattern("author[0]", "author[0]")

    def test_matches_pattern_wildcard(self):
        """Test wildcard pattern matching"""
        assert self.parser.matches_pattern("author[0].name", "author[*].name")
        assert self.parser.matches_pattern("author[5].name", "author[*].name")
        assert self.parser.matches_pattern("tags[10]", "tags[*]")

    def test_matches_pattern_multiple_wildcards(self):
        """Test multiple wildcards in pattern"""
        assert self.parser.matches_pattern(
            "author[0].identifier[2].value", "author[*].identifier[*].value"
        )

    def test_matches_pattern_different_names_fails(self):
        """Test that different names don't match"""
        assert not self.parser.matches_pattern("title", "author")
        assert not self.parser.matches_pattern("author[0].name", "author[0].value")

    def test_matches_pattern_different_lengths_fails(self):
        """Test that different path lengths don't match"""
        assert not self.parser.matches_pattern("author.name", "author")
        assert not self.parser.matches_pattern("author", "author.name")

    def test_matches_pattern_array_vs_non_array_fails(self):
        """Test that array/non-array segments don't match"""
        assert not self.parser.matches_pattern("author", "author[*]")
        assert not self.parser.matches_pattern("author[0]", "author")


class TestKeyParserIndexExtraction:
    """Test index extraction functionality"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_extract_indices_no_arrays(self):
        """Test extracting indices from non-array path"""
        indices = self.parser.extract_indices("book.chapter.title")
        assert indices == [None, None, None]

    def test_extract_indices_with_arrays(self):
        """Test extracting indices from path with arrays"""
        indices = self.parser.extract_indices("author[0].identifier[1].value")
        assert indices == [0, 1, None]

    def test_extract_indices_all_arrays(self):
        """Test extracting indices from all-array path"""
        indices = self.parser.extract_indices("items[5].tags[3]")
        assert indices == [5, 3]

    def test_extract_indices_with_wildcards(self):
        """Test that wildcards are treated as None in index extraction"""
        indices = self.parser.extract_indices("author[*].name")
        assert indices == [None, None]


class TestKeyParserMaxIndices:
    """Test max index calculation functionality"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_get_max_indices_single_array(self):
        """Test finding max index for single array level"""
        keys = ["author[0].name", "author[1].name", "author[2].name"]
        max_indices = self.parser.get_max_indices(keys, "author[*].name")
        assert max_indices == [2, None]

    def test_get_max_indices_multiple_arrays(self):
        """Test finding max indices for multiple array levels"""
        keys = [
            "author[0].identifier[0].value",
            "author[0].identifier[1].value",
            "author[1].identifier[0].value",
        ]
        max_indices = self.parser.get_max_indices(keys, "author[*].identifier[*].value")
        assert max_indices == [1, 1, None]

    def test_get_max_indices_sparse_indices(self):
        """Test max indices with sparse array usage"""
        keys = ["items[1]", "items[5]", "items[3]"]
        max_indices = self.parser.get_max_indices(keys, "items[*]")
        assert max_indices == [5]

    def test_get_max_indices_no_matching_keys(self):
        """Test max indices when no keys match pattern"""
        keys = ["title", "description"]
        max_indices = self.parser.get_max_indices(keys, "author[*].name")
        assert max_indices == [None, None]


class TestKeyParserSegmentsToString:
    """Test segments to string conversion"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_segments_to_string_simple(self):
        """Test converting simple segments to string"""
        segments = [PathSegment("title", None, False)]
        result = self.parser.segments_to_string(segments)
        assert result == "title"

    def test_segments_to_string_nested(self):
        """Test converting nested segments to string"""
        segments = [
            PathSegment("book", None, False),
            PathSegment("chapter", None, False),
            PathSegment("title", None, False),
        ]
        result = self.parser.segments_to_string(segments)
        assert result == "book.chapter.title"

    def test_segments_to_string_with_arrays(self):
        """Test converting segments with arrays to string"""
        segments = [
            PathSegment("author", 0, True),
            PathSegment("identifier", "*", True),
            PathSegment("value", None, False),
        ]
        result = self.parser.segments_to_string(segments)
        assert result == "author[0].identifier[*].value"

    def test_segments_to_string_roundtrip(self):
        """Test that parse -> to_string -> parse gives same result"""
        original = "author[5].identifier[*].value"
        segments = self.parser.parse(original)
        string = self.parser.segments_to_string(segments)
        segments2 = self.parser.parse(string)
        assert segments == segments2


class TestKeyParserEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Setup parser for each test"""
        self.parser = KeyParser()

    def test_parse_nested_brackets_raises_error(self):
        """Test that nested brackets raise invalid syntax error"""
        with pytest.raises(KeyParseError, match="Invalid segment syntax"):
            self.parser.parse("author[[0]]")

    def test_parse_very_large_index(self):
        """Test parsing very large array indices"""
        segments = self.parser.parse("items[999999]")
        assert segments[0].index == 999999

    def test_parse_class_name_index(self):
        """Test parsing class name as array index (type hint)"""
        segments = self.parser.parse("Creator[Person].name")
        assert len(segments) == 2
        assert segments[0] == PathSegment("Creator", "Person", True)
        assert segments[1] == PathSegment("name", None, False)

    def test_parse_with_hyphens(self):
        """Test parsing field names with hyphens"""
        segments = self.parser.parse("content-type")
        assert segments[0].name == "content-type"

    def test_multiple_wildcard_levels(self):
        """Test complex pattern with multiple wildcard levels"""
        path = "items[*].children[*].tags[*]"
        segments = self.parser.parse(path)
        assert len(segments) == 3
        assert all(seg.is_array and seg.index == "*" for seg in segments)
