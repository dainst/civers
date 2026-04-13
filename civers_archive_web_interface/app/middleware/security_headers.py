"""
Security Headers Middleware

Adds security headers including Content Security Policy (CSP) for iframe protection
and other security-related headers to prevent XSS and clickjacking attacks.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to responses.

    Specifically configured for SingleFile iframe security while allowing
    necessary functionality for the web archive viewer.
    """

    def __init__(self, app, debug: bool = False):
        super().__init__(app)
        self.debug = debug

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers based on request path
        self._add_security_headers(request, response)

        return response

    def _add_security_headers(self, request: Request, response: Response) -> None:
        """Add appropriate security headers based on the request path."""

        path = request.url.path

        # Basic security headers for all responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS - Force HTTPS and prevent protocol downgrade attacks
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Permissions Policy - Deny unnecessary browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), fullscreen=(self)"

        # Content Security Policy
        if path.startswith("/api/artifacts/serve"):
            # For artifact serving (SingleFile HTML content)
            self._add_artifact_csp(response)
        elif path in ["/docs", "/redoc"]:
            # For API documentation (Swagger UI / ReDoc)
            self._add_docs_csp(response)
        elif path.startswith("/api/"):
            # For API endpoints
            self._add_api_csp(response)
        else:
            # For web pages
            self._add_page_csp(response)

    def _add_artifact_csp(self, response: Response) -> None:
        """CSP for serving SingleFile HTML artifacts."""
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # SingleFile HTML may contain inline scripts
            "style-src 'self' 'unsafe-inline'",   # SingleFile HTML contains inline styles
            "img-src 'self' data: blob:",         # Allow data URLs and blobs for images
            "font-src 'self' data:",              # Allow data URLs for fonts
            "connect-src 'self'",
            "frame-ancestors 'self'",             # Only allow embedding in same origin
            "object-src 'none'",                  # Disable plugins
            "base-uri 'self'",
            "form-action 'self'"
        ]

        if self.debug:
            # In debug mode, be less restrictive for development
            csp_directives.extend([
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "connect-src 'self' ws: wss:"  # Allow WebSocket connections for hot reload
            ])

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    def _add_api_csp(self, response: Response) -> None:
        """CSP for API endpoints."""
        # For API endpoints, we allow cross-origin connections for the widget
        # but keep other restrictions.
        csp_directives = [
            "default-src 'none'",
            "connect-src 'self' http://localhost:* http://127.0.0.1:*",
            "frame-ancestors 'self'"
        ]

        if self.debug:
            csp_directives = [
                "default-src 'none'",
                "connect-src *",
                "frame-ancestors *"
            ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    def _add_docs_csp(self, response: Response) -> None:
        """CSP for API documentation (Swagger UI / ReDoc)."""
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Swagger UI scripts from CDN
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",   # Swagger UI styles from CDN
            "img-src 'self' data: https://fastapi.tiangolo.com",  # FastAPI favicon and images
            "font-src 'self' https://fonts.gstatic.com",          # Web fonts if used
            "connect-src 'self'",
            "frame-ancestors 'none'",                              # Prevent embedding
            "object-src 'none'",
            "base-uri 'self'"
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    def _add_page_csp(self, response: Response) -> None:
        """CSP for web pages (HTML responses)."""
        # TODO: Consider implementing nonce-based CSP for scripts to eliminate 'unsafe-inline'
        # This would require template modifications to inject nonces into script tags
        # Base connect-src - add WebSocket in debug mode
        connect_src = "'self'"
        if self.debug:
            connect_src += " ws: wss:"  # WebSocket for hot reload

        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",    # Alpine.js requires unsafe-eval for expression evaluation
            "style-src 'self' 'unsafe-inline'",            # Tailwind CSS (pre-built, self-hosted) + inline styles
            "img-src 'self' data:",
            "font-src 'self'",
            f"connect-src {connect_src}",
            "frame-src 'self'",                   # Allow iframes from same origin (SingleFile viewer)
            "frame-ancestors 'self'",             # Prevent clickjacking (ZAP finding)
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)