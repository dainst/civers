"""
Key Parser Module

Parses flattened keys (e.g., 'author[0].identifier.value') into structured
path components for mapping flattened data to nested Pydantic models.

Example:
    >>> parser = KeyParser()
    >>> segments = parser.parse("author[0].identifier.value")
    >>> segments[0]
    PathSegment(name='author', index=0, is_array=True)
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PathSegment:
    """
    Represents a single segment in a flattened path.

    Attributes:
        name: The field/attribute name (e.g., 'author', 'identifier')
        index: Array index if present - int for numeric (e.g., 0, 1),
               str '*' for wildcard, None if not an array
        is_array: True if this segment has array notation (e.g., [0] or [*])

    Examples:
        PathSegment('author', 0, True)      # author[0]
        PathSegment('author', '*', True)    # author[*]
        PathSegment('name', None, False)    # name
    """

    name: str
    index: int | str | None
    is_array: bool

    def __post_init__(self):
        """Validate segment data after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Segment name cannot be empty")

        if self.is_array and self.index is None:
            raise ValueError("Array segment must have an index")

        if not self.is_array and self.index is not None:
            raise ValueError("Non-array segment cannot have an index")

        if isinstance(self.index, str) and self.index != "*":
            # Check if it's a valid class name (starts with uppercase usually, but let's be lenient)
            # The regex already enforces [a-zA-Z][a-zA-Z0-9_]*
            pass

        if isinstance(self.index, int) and self.index < 0:
            raise ValueError(f"Array index must be non-negative, got {self.index}")


class KeyParseError(Exception):
    """Raised when a key cannot be parsed due to invalid syntax."""

    pass


class KeyParser:
    """
    Parser for flattened keys with array notation.

    Supports parsing keys like:
    - Simple: 'title', 'name'
    - Nested: 'author.name', 'book.chapter.title'
    - Arrays: 'author[0]', 'tags[5]'
    - Wildcards: 'author[*]', 'tags[*]'
    - Complex: 'author[0].identifier[*].value'

    Thread-safe and reusable.
    """

    # Regex pattern for matching a segment with optional array notation
    # Matches: fieldname[index] or fieldname
    # Group 1: field name
    # Group 2: complete bracket notation [...]
    # Group 3: index inside brackets (number or *)
    SEGMENT_PATTERN = re.compile(
        r"^([a-zA-Z@_][a-zA-Z0-9@_\-]*)"  # Field name (starts with letter, @, or _)
        r"(?:\[([0-9]+|\*|[a-zA-Z][a-zA-Z0-9_]*)\])?$"  # Optional [index], [*], or [ClassName]
    )

    def parse(self, key: str) -> list[PathSegment]:
        """
        Parse a flattened key into path segments.

        Args:
            key: Flattened key string (e.g., 'author[0].identifier.value')

        Returns:
            List of PathSegment objects representing the parsed path

        Raises:
            KeyParseError: If the key has invalid syntax

        Examples:
            >>> parser = KeyParser()
            >>> parser.parse("title")
            [PathSegment(name='title', index=None, is_array=False)]

            >>> parser.parse("author[0].name")
            [PathSegment(name='author', index=0, is_array=True),
             PathSegment(name='name', index=None, is_array=False)]

            >>> parser.parse("author[*].identifier[*].value")
            [PathSegment(name='author', index='*', is_array=True),
             PathSegment(name='identifier', index='*', is_array=True),
             PathSegment(name='value', index=None, is_array=False)]
        """
        if not key or not key.strip():
            raise KeyParseError("Key cannot be empty")

        key = key.strip()
        segments: list[PathSegment] = []

        # Split by dots, but need to be careful with brackets
        parts = self._split_key(key)

        for part in parts:
            if not part:
                raise KeyParseError(f"Empty segment in key: '{key}'")

            segment = self._parse_segment(part, key)
            segments.append(segment)

        return segments

    def _split_key(self, key: str) -> list[str]:
        """
        Split key by dots, handling brackets correctly.

        Examples:
            'author.name' → ['author', 'name']
            'author[0].name' → ['author[0]', 'name']
            'a.b[5].c[*].d' → ['a', 'b[5]', 'c[*]', 'd']
        """
        parts: list[str] = []
        current = []
        bracket_depth = 0

        for char in key:
            if char == "[":
                bracket_depth += 1
                current.append(char)
            elif char == "]":
                bracket_depth -= 1
                if bracket_depth < 0:
                    raise KeyParseError(f"Unmatched closing bracket in: '{key}'")
                current.append(char)
            elif char == "." and bracket_depth == 0:
                # Dot outside brackets - segment separator
                if current:
                    parts.append("".join(current))
                    current = []
            else:
                current.append(char)

        if bracket_depth != 0:
            raise KeyParseError(f"Unmatched opening bracket in: '{key}'")

        if current:
            parts.append("".join(current))

        return parts

    def _parse_segment(self, part: str, original_key: str) -> PathSegment:
        """
        Parse a single segment part.

        Args:
            part: Single segment like 'author', 'author[0]', or 'author[*]'
            original_key: Original full key for error messages

        Returns:
            PathSegment object

        Raises:
            KeyParseError: If segment has invalid syntax
        """
        match = self.SEGMENT_PATTERN.match(part)

        if not match:
            raise KeyParseError(
                f"Invalid segment syntax: '{part}' in key '{original_key}'. "
                f"Expected format: 'fieldname' or 'fieldname[index]'"
            )

        name = match.group(1)
        index_str = match.group(2)

        if index_str is None:
            # Simple segment without array notation
            return PathSegment(name=name, index=None, is_array=False)

        # Parse index
        if index_str == "*":
            index: int | str = "*"
        elif index_str.isdigit():
            index = int(index_str)
        else:
            # It's a class name type hint
            index = index_str

        return PathSegment(name=name, index=index, is_array=True)

    def matches_pattern(self, key: str, pattern: str) -> bool:
        """
        Check if a concrete key matches a wildcard pattern.

        A pattern matches a key if:
        - They have the same number of segments
        - Each segment name matches
        - Numeric indices in the key match wildcards in the pattern
        - Wildcards in the pattern match any numeric index in the key

        Args:
            key: Concrete key (e.g., 'author[0].name')
            pattern: Pattern with wildcards (e.g., 'author[*].name')

        Returns:
            True if key matches pattern, False otherwise

        Examples:
            >>> parser = KeyParser()
            >>> parser.matches_pattern("author[0].name", "author[*].name")
            True
            >>> parser.matches_pattern("author[5].identifier.value", "author[*].identifier.value")
            True
            >>> parser.matches_pattern("title", "author[*].name")
            False
            >>> parser.matches_pattern("author[0].name", "author[0].name")
            True
        """
        try:
            key_segments = self.parse(key)
            pattern_segments = self.parse(pattern)
        except KeyParseError:
            return False

        # Must have same number of segments
        if len(key_segments) != len(pattern_segments):
            return False

        # Check each segment
        for key_seg, pat_seg in zip(key_segments, pattern_segments, strict=False):
            # Names must match exactly
            if key_seg.name != pat_seg.name:
                return False

            # Both must be arrays or both must not be arrays
            if key_seg.is_array != pat_seg.is_array:
                return False

            # If both are arrays, check index compatibility
            if key_seg.is_array:
                # Wildcard in pattern matches any numeric index in key
                if pat_seg.index == "*":
                    if not isinstance(key_seg.index, int) and key_seg.index != "*":
                        return False
                # Exact index match
                elif key_seg.index != pat_seg.index:
                    return False

        return True

    def extract_indices(self, key: str) -> list[int | None]:
        """
        Extract numeric array indices from a key.

        Useful for determining which list elements to access/create.

        Args:
            key: Flattened key (e.g., 'author[0].identifier[1].value')

        Returns:
            List of indices (None for non-array segments)

        Examples:
            >>> parser = KeyParser()
            >>> parser.extract_indices("author[0].identifier[1].value")
            [0, 1, None]
            >>> parser.extract_indices("title")
            [None]
        """
        segments = self.parse(key)
        return [seg.index if isinstance(seg.index, int) else None for seg in segments]

    def get_max_indices(self, keys: list[str], pattern: str) -> list[int | None]:
        """
        Find maximum index at each array level for keys matching a pattern.

        Useful for determining how many list elements to create.

        Args:
            keys: List of concrete keys
            pattern: Pattern to match against

        Returns:
            List of max indices (None for non-array segments)

        Examples:
            >>> parser = KeyParser()
            >>> keys = ["author[0].name", "author[1].name", "author[2].name"]
            >>> parser.get_max_indices(keys, "author[*].name")
            [2, None]  # Max index is 2 for author, name is not an array
        """
        pattern_segments = self.parse(pattern)
        max_indices: list[int | None] = [None] * len(pattern_segments)

        for key in keys:
            if not self.matches_pattern(key, pattern):
                continue

            key_segments = self.parse(key)
            for i, seg in enumerate(key_segments):
                if isinstance(seg.index, int):
                    current_max = max_indices[i]
                    if current_max is None or seg.index > current_max:
                        max_indices[i] = seg.index

        return max_indices

    def segments_to_string(self, segments: list[PathSegment]) -> str:
        """
        Convert a list of PathSegments back to a string representation.
        """
        parts = []
        for seg in segments:
            part = seg.name
            if seg.is_array:
                part += f"[{seg.index}]"
            parts.append(part)
        return ".".join(parts)
