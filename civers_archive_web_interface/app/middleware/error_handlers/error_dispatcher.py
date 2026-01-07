"""
Error Dispatcher Middleware

This middleware acts as a router that decides which specialized error handler
to invoke based on the request path. This eliminates the inefficiency of
running multiple middleware while maintaining clean separation of concerns.

Architecture:
- Single middleware in the stack
- Single path check to determine handler
- Delegates to specialized handler classes (not middleware)
- Maintains clean separation for future microservices split
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from asgi_correlation_id.context import correlation_id

from .api_error_handler import APIErrorHandler
from .page_error_handler import PageErrorHandler
from ...constants import API_PREFIX, FASTAPI_API_PATHS

logger = logging.getLogger(__name__)


class ErrorDispatcherMiddleware(BaseHTTPMiddleware):
    """
    Middleware that routes requests to appropriate error handlers.

    This middleware performs a single path check and delegates error handling
    to specialized handler classes based on whether the request is for an API
    endpoint (/api/*) or a page route.

    Benefits:
    - Only one middleware execution per request
    - Single path check instead of multiple redundant checks
    - Clean separation of API and page error handling logic
    - Easy to extract handlers for microservices architecture
    """

    def __init__(self, app):
        super().__init__(app)
        # Initialize specialized error handlers
        self.api_handler = APIErrorHandler()
        self.page_handler = PageErrorHandler()

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Route request to appropriate error handler based on path.

        Performs single path check to determine if request should be handled
        by API error handler (JSON responses) or page error handler (HTML responses).
        """
        # Debug: Check correlation_id availability
        logger.debug(f"ErrorDispatcher ENTRY - correlation_id: {correlation_id.get('not_available')}")

        # Single path check to determine handler
        if (request.url.path.startswith(f'{API_PREFIX}/') or
            request.url.path in FASTAPI_API_PATHS):
            # API request - use API error handler for JSON responses
            handler = self.api_handler
            logger.debug(f"Routing API request to APIErrorHandler: {request.url.path}")
        else:
            # Page request - use page error handler for HTML responses
            handler = self.page_handler
            logger.debug(f"Routing page request to PageErrorHandler: {request.url.path}")

        # Delegate to appropriate handler
        return await handler.handle_request(request, call_next)