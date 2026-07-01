"""
API Error Handler

This handler processes all errors for API routes (/api/*) and returns
consistent JSON error responses. This separation allows for easy splitting
of API and frontend services in the future.
"""

from typing import Optional
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from ...storage import StorageError
from ...utils.security import SecurityValidationError
from ...models.responses import ErrorResponse, ErrorDetail
from ...custom_exceptions.exceptions.api_exceptions import ResourceNotFoundError, ArtifactNotFoundError, ValidationError
from ...utils.correlation import get_correlation_id


logger = logging.getLogger(__name__)


def create_api_error_response(
    error_type: str,
    message: str,
    status_code: int,
    details: Optional[list[ErrorDetail]] = None
) -> JSONResponse:
    """Create consistent API error response using Pydantic ErrorResponse model."""

    request_id = get_correlation_id()
    error_response = ErrorResponse(
        success=False,
        error=error_type,
        message=message,
        details=details,
        request_id=request_id
    )
    response = JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )
    # Add request ID to headers for consistency
    response.headers["X-Request-ID"] = request_id
    return response


class APIErrorHandler:
    """
    Handler to process errors for API routes only.

    This handler processes API requests and returns JSON error responses.
    """

    async def handle_request(self, request: Request, call_next) -> Response:
        """Handle API request and process any errors that occur."""
        try:
            response = await call_next(request)

            # Handle 404 responses for API routes
            if response.status_code == 404:
                return await self._handle_api_404(request)

            return response

        except HTTPException as exc:
            return await self._handle_http_exception(request, exc)
        except RequestValidationError as exc:
            return await self._handle_validation_error(request, exc)
        except ResourceNotFoundError as exc:
            return await self._handle_resource_not_found_error(request, exc)
        except ArtifactNotFoundError as exc:
            return await self._handle_artifact_not_found_error(request, exc)
        except ValidationError as exc:
            return await self._handle_api_validation_error(request, exc)
        except StorageError as exc:
            return await self._handle_storage_error(request, exc)
        except SecurityValidationError as exc:
            return await self._handle_security_error(request, exc)
        except Exception as exc:
            return await self._handle_general_error(request, exc)

    async def _handle_api_404(self, request: Request) -> JSONResponse:
        """Handle 404 errors for API routes."""
        logger.warning("API endpoint not found", extra={
            'status_code': 404,
            'error_type': 'api_not_found',
            'path': request.url.path
        })

        return create_api_error_response(
            error_type="not_found",
            message="API endpoint not found",
            status_code=404
        )

    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions for API routes."""

        # Map common HTTP status codes to error types
        error_type_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limit_exceeded",
            500: "internal_error",
            502: "bad_gateway",
            503: "service_unavailable"
        }

        error_type = error_type_map.get(exc.status_code, "http_error")

        # Log the error
        if exc.status_code >= 500:
            logger.error(f"API HTTP {exc.status_code}: {exc.detail}", extra={
                'status_code': exc.status_code,
                'error_type': error_type,
                'path': request.url.path
            })
        else:
            logger.warning(f"API HTTP {exc.status_code}: {exc.detail}", extra={
                'status_code': exc.status_code,
                'error_type': error_type,
                'path': request.url.path
            })

        # Handle ErrorDetail objects properly
        details = None
        if isinstance(exc.detail, ErrorDetail):
            details = [exc.detail]
        elif isinstance(exc.detail, list) and all(isinstance(d, ErrorDetail) for d in exc.detail):
            details = exc.detail

        return create_api_error_response(
            error_type=error_type,
            message=str(exc.detail),
            status_code=exc.status_code,
            details=details
        )

    async def _handle_validation_error(self, request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle FastAPI validation errors for API routes."""

        # Extract validation details as ErrorDetail objects
        validation_details = []
        for error in exc.errors():
            field_name = " -> ".join(str(loc) for loc in error["loc"])
            error_detail = ErrorDetail(
                field=field_name,
                message=error["msg"],
                code=error["type"]
            )
            validation_details.append(error_detail)

        # Log validation error
        logger.warning("API request validation failed", extra={
            'error_type': 'api_validation_error',
            'path': request.url.path,
            'validation_errors': [detail.model_dump() for detail in validation_details]
        })

        return create_api_error_response(
            error_type="validation_error",
            message="Request validation failed",
            status_code=422,
            details=validation_details,
        )

    async def _handle_resource_not_found_error(self, request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        """Handle ResourceNotFoundError for API routes."""
        logger.info(f"API resource not found: {exc.resource_type} '{exc.resource_id}'", extra={
            'error_type': 'api_resource_not_found',
            'path': request.url.path,
            'resource_type': exc.resource_type,
            'resource_id': exc.resource_id
        })

        # Create ErrorDetail for the not found resource
        error_detail = ErrorDetail(
            field=exc.resource_type.lower() + "_id",
            message=str(exc),
            code=f"{exc.resource_type.lower()}_not_found"
        )

        return create_api_error_response(
            error_type="not_found",
            message=str(exc),
            status_code=404,
            details=[error_detail],
        )

    async def _handle_artifact_not_found_error(self, request: Request, exc: ArtifactNotFoundError) -> JSONResponse:
        """Handle ArtifactNotFoundError for API routes."""
        logger.warning(f"API artifact not found: {exc.artifact_type} for snapshot {exc.snapshot_id}", extra={
            'error_type': 'api_artifact_not_found',
            'path': request.url.path,
            'artifact_type': exc.artifact_type,
            'snapshot_id': exc.snapshot_id
        })

        # Create ErrorDetail for the not found artifact
        error_detail = ErrorDetail(
            field="artifact",
            message=str(exc),
            code="artifact_not_found"
        )

        return create_api_error_response(
            error_type="not_found",
            message=str(exc),
            status_code=404,
            details=[error_detail],
        )

    async def _handle_api_validation_error(self, request: Request, exc: ValidationError) -> JSONResponse:
        """Handle custom ValidationError for API routes."""
        logger.warning(f"API validation error: {exc}", extra={
            'error_type': 'api_custom_validation_error',
            'path': request.url.path,
            'field': exc.field
        })

        # Create ErrorDetail for the validation error
        error_detail = ErrorDetail(
            field=exc.field,
            message=str(exc),
            code="validation_error"
        )

        return create_api_error_response(
            error_type="validation_error",
            message=str(exc),
            status_code=400,
            details=[error_detail],
        )

    async def _handle_storage_error(self, request: Request, exc: StorageError) -> JSONResponse:
        """Handle storage-related errors for API routes."""

        # Map storage error types
        if "not found" in str(exc).lower():
            error_type = "not_found"
            status_code = 404
            message = "Requested resource not found"
        elif "permission" in str(exc).lower() or "access" in str(exc).lower():
            error_type = "forbidden"
            status_code = 403
            message = "Access to resource not allowed"
        else:
            error_type = "storage_error"
            status_code = 500
            message = "Storage operation failed"

        # Log storage error
        if status_code >= 500:
            logger.error(f"API storage error: {exc}", extra={
                'error_type': f'api_{error_type}',
                'path': request.url.path,
                'storage_error': str(exc)
            })
        else:
            logger.warning(f"API storage error: {exc}", extra={
                'error_type': f'api_{error_type}',
                'path': request.url.path,
                'storage_error': str(exc)
            })

        # Create ErrorDetail for storage error
        storage_error_detail = ErrorDetail(
            field=None,
            message=str(exc),
            code="storage_error"
        )

        return create_api_error_response(
            error_type=error_type,
            message=message,
            status_code=status_code,
            details=[storage_error_detail]
        )

    async def _handle_security_error(self, request: Request, exc: SecurityValidationError) -> JSONResponse:
        """Handle security validation errors for API routes."""

        # Log security error (important for monitoring)
        logger.warning(f"API security validation failed: {exc}", extra={
            'error_type': 'api_security_validation_error',
            'path': request.url.path,
            'client_ip': request.client.host if request.client else "unknown",
            'security_error': str(exc)
        })

        # Create ErrorDetail for security error
        security_error_detail = ErrorDetail(
            field=None,
            message=str(exc),
            code="security_validation_error"
        )

        return create_api_error_response(
            error_type="security_validation_error",
            message="Security validation failed",
            status_code=400,
            details=[security_error_detail]
        )

    async def _handle_general_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions for API routes."""

        # Log the full exception for debugging
        logger.error(f"API unhandled exception: {exc}", extra={
            'error_type': f"api_{type(exc).__name__}",
            'path': request.url.path,
            'exception_details': str(exc)
        }, exc_info=True)

        # Return generic error to avoid information disclosure
        return create_api_error_response(
            error_type="internal_error",
            message="An unexpected error occurred",
            status_code=500,
            details=None
        )