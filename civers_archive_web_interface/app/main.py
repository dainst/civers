from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from asgi_correlation_id import CorrelationIdMiddleware
import os
from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError
from .custom_exceptions.handlers import custom_validation_exception_handler

from .api.urls import router as urls_router
from .api.snapshot_detail import router as snapshots_router
from .api.artifacts import router as artifacts_router
from .api.upload import router as upload_router
from .api.archive_request import router as archive_request_router
from .api.webhook import router as webhook_router
from .api.widget import router as widget_router
from .routes.pages import router as pages_router
from configs import load_app_config, ConfigurationError
from .storage import create_storage_service
from .database.sqlite_manager import SQLiteManager
from .database.models import get_schema_sql
from .middleware import (
    ErrorDispatcherMiddleware,
    SecurityHeadersMiddleware
)
from .logging import configure_logging
from .constants import HealthStatus
import uvicorn
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure logging at startup (before loading config to see setup logs)
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", None)
json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"
configure_logging(level=log_level, json_format=json_logging, log_file=log_file)

# Load application configuration at module level for FastAPI initialization
# This allows using config values before the lifespan context runs
_app_config = load_app_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Import services here to avoid circular imports
    from .services import DomainService, KafkaProducerService, RequestStatusService
    
    # Startup
    try:
        # Store app configuration in app state (already loaded at module level)
        app.state.app_config = _app_config
        
        # Create storage service with configuration
        storage_service = create_storage_service(_app_config)
        app.state.storage_service = storage_service
        
        # Initialize database for request status tracking
        # Re-use storage provider's DB if it's SQLite, otherwise create separate connection
        db_manager = None
        if hasattr(storage_service.provider, 'db') and isinstance(storage_service.provider.db, SQLiteManager):
            db_manager = storage_service.provider.db
            logger.info("Using storage provider's SQLite database for request status tracking")
        elif hasattr(_app_config.storage, 'sqlite') and _app_config.storage.sqlite:
            # Create a separate DB manager for status tracking
            db_path = Path(_app_config.storage.sqlite.db_path)
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            
            db_manager = SQLiteManager(db_path)
            db_manager.connect()
            db_manager.initialize_schema(get_schema_sql())
            logger.info(f"Created separate SQLite database for status tracking at {db_path}")
        
        if db_manager:
            app.state.request_status_service = RequestStatusService(db_manager)
            logger.info("Request status service initialized")
        else:
            logger.warning("No database available for request status tracking")
        
        # Initialize domain service for archive request form
        domain_service = DomainService(_app_config.domains)
        app.state.domain_service = domain_service
        
        domain_names = [d.name for d in domain_service.domains]
        enabled_count = len(domain_service.get_enabled_domains(include_wildcards=True, include_default=True))
        logger.info(f"Domain service loaded {len(domain_service.domains)} domains ({enabled_count} enabled): {domain_names}")
        # Initialize Kafka producer service (optional - for archive request submission)
        kafka_producer = KafkaProducerService(
            _app_config.transport.kafka, 
            enabled=_app_config.transport.kafka_enabled
        )
        app.state.kafka_producer = kafka_producer
        
        if kafka_producer.is_enabled:
            # Attempt to initialize (will log warning if Kafka not available)
            kafka_initialized = await kafka_producer.initialize()
            if kafka_initialized:
                logger.info("Kafka producer initialized")
            else:
                logger.warning("Kafka producer not initialized - archive request submission disabled")
        else:
            logger.info("Kafka disabled in configuration")
        
        logger.info("Application initialized successfully")
        
    except ConfigurationError as e:
        logger.error(f"Failed to initialize application: {e}")
        raise RuntimeError(f"Application initialization failed: {e}") from e
    
    yield
    
    # Shutdown (cleanup services)
    logger.info("Application shutting down...")
    
    # Shutdown Kafka producer gracefully
    if hasattr(app.state, 'kafka_producer') and app.state.kafka_producer:
        await app.state.kafka_producer.shutdown()
    
    logger.info("Application shutdown complete")

# Create FastAPI application using config values
app = FastAPI(
    title=_app_config.app.name,
    description=_app_config.app.description,
    version=_app_config.app.version,
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

# CORS configuration for the external widget
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be a whitelist of authorized domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)     # Correlation ID for request tracing (outermost)

# Register application-level exception handlers for consistent error formatting
app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)

# Configure Jinja2 templates with auto-reload in debug mode
debug = os.getenv("DEBUG", "False").lower() == "true"
templates = Jinja2Templates(directory=_app_config.directories.templates, auto_reload=debug)

# Mount static files
app.mount("/static", StaticFiles(directory=_app_config.directories.static), name="static")

# Include API routers
app.include_router(urls_router)
app.include_router(snapshots_router)
app.include_router(artifacts_router)
app.include_router(upload_router)
app.include_router(archive_request_router)
app.include_router(webhook_router)
app.include_router(widget_router)

# Include page routers
app.include_router(pages_router)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and deployment validation"""
    return {
        "status": HealthStatus.HEALTHY,
        "service": _app_config.app.service_name,
        "version": _app_config.app.version
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
