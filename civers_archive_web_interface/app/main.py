from contextlib import asynccontextmanager
from venv import logger
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from asgi_correlation_id import CorrelationIdMiddleware
import os
from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError
from .custom_exceptions.handlers import custom_validation_exception_handler

from .api.urls import router as urls_router
from .api.snapshot_detail import router as snapshots_router
from .api.artifacts import router as artifacts_router
from .api.upload import router as upload_router
from .routes.pages import router as pages_router
from .config import load_app_config, ConfigurationError
from .storage import create_storage_service
from .middleware import (
    ErrorDispatcherMiddleware,
    SecurityHeadersMiddleware
)
from .logging import configure_logging
import uvicorn
import logging

logger = logging.getLogger(__name__)
# Load environment variables
load_dotenv()

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", None)
json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"

# Configure logging at startup
configure_logging(level=log_level, json_format=json_logging, log_file=log_file)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    try:
        # Load application configuration
        app_config = load_app_config()
        app.state.app_config = app_config
        
        # Create storage service with configuration
        storage_service = create_storage_service(app_config)
        app.state.storage_service = storage_service
        
        # Get logger after middleware has set up logging
        
        logger.debug("Application initialized successfully")
    except ConfigurationError as e:
        # Get logger after middleware has set up logging
        
        logger.error(f"Failed to initialize application: {e}")
        raise RuntimeError(f"Application initialization failed: {e}") from e
    
    yield
    
    # Shutdown (cleanup if needed)
    logger.debug("Application shutting down")

# Create FastAPI application
app = FastAPI(
    title="Civers Archive Web Interface",
    description="MVP for browsing and replaying archived versions of websites",
    version="1.0.0",
    lifespan=lifespan
)

"""
Add middleware in order (last added = first executed)
For example:

app.add_middleware(MiddlewareA)
app.add_middleware(MiddlewareB)

This results in the following execution order:

    Request: MiddlewareB → MiddlewareA → route

    Response: route → MiddlewareA → MiddlewareB
"""
app.add_middleware(ErrorDispatcherMiddleware)  # Single dispatcher for all error handling
app.add_middleware(
    SecurityHeadersMiddleware,
    debug=os.getenv("DEBUG", "False").lower() == "true"
)  # Security headers for CSP and XSS protection
app.add_middleware(CorrelationIdMiddleware)     # Correlation ID for request tracing (outermost)

# Register application-level exception handlers for consistent error formatting
app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)

# Configure Jinja2 templates with auto-reload in debug mode
debug = os.getenv("DEBUG", "False").lower() == "true"
templates = Jinja2Templates(directory="templates", auto_reload=debug)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routers
app.include_router(urls_router)
app.include_router(snapshots_router)
app.include_router(artifacts_router)
app.include_router(upload_router)

# Include page routers
app.include_router(pages_router)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and deployment validation"""
    return {
        "status": "healthy",
        "service": "civers-archive-web-interface",
        "version": "1.0.0"
    }

@app.get("/debug/cache/stats", include_in_schema=False, tags=["Debug"])
async def cache_stats(request: Request):
    """
    Get storage cache statistics.
    
    **Development and Testing Purpose Only**
    
    This endpoint provides internal cache statistics for development, 
    debugging, and testing purposes. It should not be used in production
    applications and may be removed or restricted in future versions.
    """
    storage_service = request.app.state.storage_service
    return storage_service.get_cache_stats()

# Home page route is now handled by pages_router

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    uvicorn.run("app.main:app", host=host, port=port, reload=debug)