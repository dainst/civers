"""
Shared correlation ID utility.

Provides a single helper for reading the current request's correlation ID
from the asgi-correlation-id context. Used by both API and page error handlers.
"""

from asgi_correlation_id.context import correlation_id


def get_correlation_id() -> str:
    """Get correlation ID from asgi-correlation-id context, defaulting to 'unknown'."""
    return correlation_id.get('unknown')
