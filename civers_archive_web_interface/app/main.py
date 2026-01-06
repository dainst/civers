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
from .api.archive_request import router as archive_request_router
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
    # Import services here to avoid circular imports
    from .services import DomainService, KafkaProducerService, RequestStatusService
    
    # Startup
    try:
        # Load application configuration
        app_config = load_app_config()
        app.state.app_config = app_config
        
        # Create storage service with configuration
        storage_service = create_storage_service(app_config)
        app.state.storage_service = storage_service
        
        # Initialize database for request status tracking
        # Re-use storage provider's DB if it's SQLite, otherwise create separate connection
        db_manager = None
        if hasattr(storage_service.provider, 'db') and isinstance(storage_service.provider.db, SQLiteManager):
            db_manager = storage_service.provider.db
            logger.info("Using storage provider's SQLite database for request status tracking")
        elif app_config.storage.sqlite:
            # Create a separate DB manager for status tracking
            from pathlib import Path
            db_path = Path(app_config.storage.sqlite.db_path)
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            
            db_manager = SQLiteManager(db_path)
            db_manager.connect()
            db_manager.initialize_schema(get_schema_sql())
            logger.info(f"Created separate SQLite database for status tracking at {db_path}")
        
        if db_manager:
            app.state.request_status_service = RequestStatusService(db_manager)
            logger.info("✅ Request status service initialized")
        else:
            logger.warning("⚠️ No database available for request status tracking")
        
        # Initialize domain service for archive request form
        domain_service = DomainService(app_config.domains)
        app.state.domain_service = domain_service
        
        logger.info(f"✅ Domain service loaded {len(domain_service.domains)} domains")
        # Initialize Kafka producer service (optional - for archive request submission)
        kafka_producer = KafkaProducerService(app_config.kafka)
        app.state.kafka_producer = kafka_producer
        
        if kafka_producer.is_enabled:
            # Attempt to initialize (will log warning if Kafka not available)
            kafka_initialized = await kafka_producer.initialize()
            if kafka_initialized:
                logger.info("✅ Kafka producer initialized")
            else:
                logger.warning("⚠️ Kafka producer not initialized - archive request submission disabled")
        else:
            logger.info("📭 Kafka disabled in configuration")
        
        logger.info("✅ Application initialized successfully")
        
    except ConfigurationError as e:
        logger.error(f"Failed to initialize application: {e}")
        raise RuntimeError(f"Application initialization failed: {e}") from e
    
    yield
    
    # Shutdown (cleanup services)
    logger.info("🛑 Application shutting down...")
    
    # Shutdown Kafka producer gracefully
    if hasattr(app.state, 'kafka_producer') and app.state.kafka_producer:
        await app.state.kafka_producer.shutdown()
    
    logger.info("✅ Application shutdown complete")

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
app.include_router(archive_request_router)

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