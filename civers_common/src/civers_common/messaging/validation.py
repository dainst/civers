"""Shared validation for values that cross the wire into log fields and file paths.
"""

import re

_REQUEST_ID_RE = re.compile(r"[a-zA-Z0-9_-]+")


def is_valid_request_id(value: object) -> bool:
    """Whether ``value`` is safe as a log field, a Kafka key and a path segment."""
    return isinstance(value, str) and _REQUEST_ID_RE.fullmatch(value) is not None
