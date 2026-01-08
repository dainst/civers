"""
Main application orchestrator for metadata extraction.

This follows the same architecture pattern as the archive generator
with the three-layer structure: Configuration → Metadata Extraction Service → Transport Layer.

Configuration Loading:
    Uses YamlFileConfigLoader with hierarchical config loading:
    - CONFIG_DIR: External config directory (for Docker mounts)
    - CONFIG_ENVIRONMENT: Environment selection (development, testing, docker, production)
    - Automatic environment detection (Docker, pytest)
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from configs import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services import KafkaTransportService
from metadata_extraction_services import MetadataExtractionService



# Configure logging with Kafka suppression
log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
setup_logging(level=log_level, log_file='metadata_extractor.log', suppress_kafka_logs=True)

logger = get_logger(__name__)


class MetadataExtractionApp:
    """Main application using the metadata extraction service architecture."""
    
    def __init__(self, config_loader: Optional[YamlFileConfigLoader] = None):
        self.config = None
        self.config_loader = config_loader
        self.kafka_transport: Optional[KafkaTransportService] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the application components."""
        try:
            logger.info("🚀 Initializing Metadata Extraction Application...")
            
            # Load configuration using hierarchical loader
            logger.info("📄 Loading configuration using YamlFileConfigLoader")
            try:
                if not self.config_loader:
                    self.config_loader = YamlFileConfigLoader()
                logger.info(f"🌍 Detected environment: {self.config_loader.environment}")
                logger.info(f"📁 Config directory: {self.config_loader.config_dir}")
                self.config = self.config_loader.load()
                logger.info("✅ Configuration loaded and validated successfully")
            except FileNotFoundError as e:
                logger.error(f"❌ Configuration file not found: {e}")
                raise RuntimeError(f"Configuration loading failed: {e}") from e
            except Exception as e:
                logger.error(f"❌ Configuration loading failed: {e}")
                raise RuntimeError(f"Configuration loading failed: {e}") from e
            logger.info(f"   App: {self.config.app.name} v{self.config.app.version}")
            
            # Log transport configuration
            if self.config.app.transport and self.config.app.transport.kafka:
                logger.info(f"   Kafka: {self.config.app.transport.kafka.bootstrap_servers}")
            else:
                logger.warning("⚠️ No Kafka transport configuration found")
            
            logger.info(f"   Domains: {[d.name for d in self.config.domains]}")
            
            # Create Metadata Extraction Service
            logger.info("🔧 Creating metadata extraction service...")
            metadata_service = MetadataExtractionService(self.config)
            logger.info("✅ Metadata extraction service created")
            
            # Create Kafka transport service
            logger.info("🔧 Creating Kafka transport service...")
            self.kafka_transport = KafkaTransportService(self.config, metadata_service)
            logger.info("✅ Kafka transport service created")
            logger.info(f"   Bootstrap servers: {self.config.app.get_kafka_config().bootstrap_servers}")
            
            # Perform metadata service basic check
            try:
                # Check if config model is working by getting supported domains
                supported_domains = metadata_service.config_data_model.get_supported_domains()
                logger.info("✅ Metadata extraction service initialized successfully")
                logger.info(f"   Supported domains: {len(supported_domains)}")
                if supported_domains:
                    logger.info(f"   Sample domains: {supported_domains[:3]}")
            except Exception as e:
                logger.warning(f"⚠️ Metadata extraction service check failed: {e}")
            
            logger.info("🎉 Application initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize application: {e}", exc_info=True)
            return False
    
    async def start(self):
        """Start the application."""
        if not await self.initialize():
            logger.error("❌ Application initialization failed")
            return False
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        self.running = True
        logger.info("🚀 Starting Metadata Extraction Application...")
        logger.info("📡 Listening for metadata extraction requests via Kafka transport...")
        
        try:
            # Start the Kafka transport service (this will block until shutdown)
            transport_task = asyncio.create_task(self.kafka_transport.start())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            # Wait for either transport to finish or shutdown signal
            _, pending = await asyncio.wait(
                [transport_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logger.info("✅ Application stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Application error: {e}", exc_info=True)
            return False
        finally:
            await self.cleanup()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, _):
            logger.info(f"📡 Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()

        
        # Register signal handlers
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, signal_handler)
        
        logger.info("📡 Signal handlers registered (SIGTERM, SIGINT)")
    
    async def shutdown(self):
        """Shutdown the application gracefully, programatically"""
        logger.info("🛑 Shutting down Metadata Extraction Application...")
        self.running = False
        self._shutdown_event.set()
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("🧹 Cleaning up resources...")
        
        if self.kafka_transport:
            await self.kafka_transport.stop()
            logger.info("✅ Kafka transport service stopped")
        
        logger.info("✅ Cleanup completed")

async def main_async(app: Optional[MetadataExtractionApp] = None):
    """Asynchronous entry point for the application."""
    try:
        if app is None:
            app = MetadataExtractionApp()
        logger.info("🎯 Starting Metadata Extraction Application")
        success = await app.start()
        if success:
            logger.info("👋 Metadata Extraction Application finished successfully")
        else:
            logger.error("❌ Metadata Extraction Application finished with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Application interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

def main():
    """Sync wrapper for script entry point."""
    asyncio.run(main_async())

if __name__ == "__main__":
    logger.info("🎯 Metadata Extractor - Event-Driven Metadata Processing")
    logger.info("="*60)
    
    # Log environment detection info
    env = os.getenv("CONFIG_ENVIRONMENT", "auto-detect")
    config_dir = os.getenv("CONFIG_DIR", "configs/data (default)")
    logger.info(f"   CONFIG_ENVIRONMENT: {env}")
    logger.info(f"   CONFIG_DIR: {config_dir}")
    logger.info("="*60)
    
    asyncio.run(main_async())
