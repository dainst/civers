"""Tests for the shared request_id check (civers_common.messaging.validation).

One definition, used by the transport spine and by every service's wire models. The
value ends up in log records, as a Kafka key, and as a path segment, so what it admits
is a security boundary rather than a formatting preference.
"""

import pytest

from civers_common import is_valid_request_id


class TestAccepts:
    @pytest.mark.parametrize(
        "value", ["abc", "r1", "req-123", "req_123", "ABC-def_456", "0"]
    )
    def test_alphanumerics_hyphens_and_underscores(self, value):
        assert is_valid_request_id(value)


class TestRejects:
    @pytest.mark.parametrize(
        "value",
        [
            "abc\n",      # '$' also matches before a trailing newline — log injection
            "\nabc",
            "a\r\nb",
            "abc\n\n",
            "a b",
            "../etc/passwd",
            "a/b",
            "",
            "   ",
            "abc\x00",
        ],
    )
    def test_anything_that_could_escape_a_log_line_or_a_path(self, value):
        assert not is_valid_request_id(value)

    @pytest.mark.parametrize("value", [None, 42, b"abc", ["abc"], {"a": 1}])
    def test_non_strings(self, value):
        assert not is_valid_request_id(value)
