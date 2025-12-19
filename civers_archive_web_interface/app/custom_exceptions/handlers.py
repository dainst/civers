"""
Application-level exception handlers.

These handlers override FastAPI's default exception handling to ensure consistent
error response formatting across all endpoints. They work at the application level
to catch exceptions that occur during the routing phase, before middleware execution.

Why this is needed alongside ErrorDispatcherMiddleware:

FastAPI Request Processing Order:
1. Routing Layer (parameter validation, route matching)
   ├─ RequestValidationError raised here if required params missing
   └─ HTTPException can be raised here by FastAPI internals
2. Middleware Stack (our ErrorDispatcherMiddleware executes here)
3. Route Handler (our endpoint functions execute here)

Since validation errors occur at step 1, our middleware at step 2 never gets
the chance to handle them. These application-level handlers catch routing-phase
exceptions and route them through our middleware's error handling logic to
maintain consistent response formatting.
"""

import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from ..middleware import APIErrorHandler

async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Override FastAPI's default RequestValidationError handler.

    Routes validation errors through our middleware's error handling to maintain
    consistent error response format across all API endpoints.

    Args:
        request: The FastAPI request object
        exc: The RequestValidationError exception

    Returns:
        JSON response with consistent error format for API routes,
        FastAPI default format for page routes
    """
    logger = logging.getLogger(__name__)
    logger.error("Custom validation exception handler invoked")
    # For API routes, use our middleware's validation error handler

    if request.url.path.startswith('/api/'):
        api_handler = APIErrorHandler()
        return await api_handler._handle_validation_error(request, exc)

    # For non-API routes (pages), use FastAPI's default handler
    return await request_validation_exception_handler(request, exc)


