"""
Page Error Handler

This handler processes all errors for page routes (non-API) and returns
HTML error responses with user-friendly templates. This separation allows
for easy splitting of API and frontend services in the future.
"""

from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
import logging
from ...storage import StorageError
from ...utils.security import SecurityValidationError
from ...utils.correlation import get_correlation_id


logger = logging.getLogger(__name__)


class PageErrorHandler:
    """
    Handler to process errors for page routes (non-API).

    This handler processes non-API requests and returns HTML
    error responses with user-friendly templates.
    """

    def __init__(self):
        self.templates = Jinja2Templates(directory="templates")

    async def handle_request(self, request: Request, call_next) -> Response:
        """Handle page request and process any errors that occur."""
        try:
            response = await call_next(request)

            # Handle 404 responses for page routes
            if response.status_code == 404:
                return await self._handle_page_404(request)

            return response

        except HTTPException as exc:
            return await self._handle_http_exception(request, exc)
        except StorageError as exc:
            return await self._handle_storage_error(request, exc)
        except SecurityValidationError as exc:
            return await self._handle_security_error(request, exc)
        except Exception as exc:
            return await self._handle_general_error(request, exc)

    async def _handle_page_404(self, request: Request) -> Response:
        """Handle 404 errors for page routes with HTML template."""
        logger.warning("Page not found", extra={
            'status_code': 404,
            'error_type': "page_not_found",
            'path': request.url.path
        })

        context = {
            "request": request,
            "title": "Page Not Found - Civers Archive"
        }

        response = self.templates.TemplateResponse("404.html", context, status_code=404)
        response.headers["X-Request-ID"] = get_correlation_id()
        return response

    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> Response:
        """Handle FastAPI HTTP exceptions for page routes."""

        if exc.status_code >= 500:
            logger.error(f"Page HTTP {exc.status_code}: {exc.detail}", extra={
                'status_code': exc.status_code,
                'error_type': "page_http_error",
                'path': request.url.path
            })
        else:
            logger.warning(f"Page HTTP {exc.status_code}: {exc.detail}", extra={
                'status_code': exc.status_code,
                'error_type': "page_http_error",
                'path': request.url.path
            })

        # Handle different HTTP status codes
        if exc.status_code == 404:
            context = {
                "request": request,
                "title": "Page Not Found - Civers Archive"
            }
            response = self.templates.TemplateResponse("404.html", context, status_code=404)
            response.headers["X-Request-ID"] = get_correlation_id()
            return response

        elif exc.status_code == 403:
            context = {
                "request": request,
                "title": "Access Forbidden - Civers Archive",
                "error_message": "You don't have permission to access this page.",
                "error_code": 403
            }
            # Could create a 403.html template in the future
            response = self.templates.TemplateResponse("404.html", context, status_code=403)
            response.headers["X-Request-ID"] = get_correlation_id()
            return response

        elif exc.status_code >= 500:
            context = {
                "request": request,
                "title": "Server Error - Civers Archive",
                "error_message": "An internal server error occurred. Please try again later.",
                "error_code": exc.status_code
            }
            # Could create a 500.html template in the future
            response = self.templates.TemplateResponse("404.html", context, status_code=exc.status_code)
            response.headers["X-Request-ID"] = get_correlation_id()
            return response

        else:
            # For other HTTP errors, use the 404 template as fallback
            context = {
                "request": request,
                "title": f"Error {exc.status_code} - Civers Archive",
                "error_message": str(exc.detail),
                "error_code": exc.status_code
            }
            response = self.templates.TemplateResponse("404.html", context, status_code=exc.status_code)
            response.headers["X-Request-ID"] = get_correlation_id()
            return response

    async def _handle_storage_error(self, request: Request, exc: StorageError) -> Response:
        """Handle storage-related errors for page routes."""

        # Map storage error types to appropriate HTTP responses
        if "not found" in str(exc).lower():
            error_type = "page_resource_not_found"
            status_code = 404
            title = "Resource Not Found - Civers Archive"
            error_message = "The requested archive or snapshot could not be found."
        elif "permission" in str(exc).lower() or "access" in str(exc).lower():
            error_type = "page_access_forbidden"
            status_code = 403
            title = "Access Forbidden - Civers Archive"
            error_message = "You don't have permission to access this resource."
        else:
            error_type = "page_storage_error"
            status_code = 500
            title = "Server Error - Civers Archive"
            error_message = "There was a problem accessing the archive. Please try again later."

        # Log storage error
        if status_code >= 500:
            logger.error(f"Page storage error: {exc}", extra={
                'error_type': error_type,
                'path': request.url.path,
                'storage_error': str(exc)
            })
        else:
            logger.warning(f"Page storage error: {exc}", extra={
                'error_type': error_type,
                'path': request.url.path,
                'storage_error': str(exc)
            })

        context = {
            "request": request,
            "title": title,
            "error_message": error_message,
            "error_code": status_code
        }

        response = self.templates.TemplateResponse("404.html", context, status_code=status_code)
        response.headers["X-Request-ID"] = get_correlation_id()
        return response

    async def _handle_security_error(self, request: Request, exc: SecurityValidationError) -> Response:
        """Handle security validation errors for page routes."""

        # Log security error (important for monitoring)
        logger.warning(f"Page security validation failed: {exc}", extra={
            'error_type': "page_security_validation_error",
            'path': request.url.path,
            'client_ip': request.client.host if request.client else "unknown",
            'security_error': str(exc)
        })

        context = {
            "request": request,
            "title": "Invalid Request - Civers Archive",
            "error_message": "The request contains invalid or potentially unsafe parameters.",
            "error_code": 400
        }

        response = self.templates.TemplateResponse("404.html", context, status_code=400)
        response.headers["X-Request-ID"] = get_correlation_id()
        return response

    async def _handle_general_error(self, request: Request, exc: Exception) -> Response:
        """Handle unexpected exceptions for page routes."""

        # Log the full exception for debugging
        logger.error(f"Page unhandled exception: {exc}", extra={
            'error_type': f"page_{type(exc).__name__}",
            'path': request.url.path,
            'exception_details': str(exc)
        }, exc_info=True)

        context = {
            "request": request,
            "title": "Server Error - Civers Archive",
            "error_message": "An unexpected error occurred. Please try again later.",
            "error_code": 500
        }

        response = self.templates.TemplateResponse("404.html", context, status_code=500)
        response.headers["X-Request-ID"] = get_correlation_id()
        return response