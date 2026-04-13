# main.py
import asyncio
import logging
import signal
import sys
from typing import Optional

from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services import KafkaTransportService
from archive_services import ArchiveService

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, log_file='archive_generator.log', suppress_kafka_logs=True)

logger = get_logger(__name__)

class ArchiveGeneratorApp:
    """Main application using the KafkaTransportService architecture."""
    
    def __init__(self):
        """Initialize the application."""
        self.config = None
        self.kafka_transport: Optional[KafkaTransportService] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the application components."""
        try:
            logger.info("🚀 Initializing Archive Generator Application...")
            
            # Load configuration using YamlFileConfigLoader
            loader = YamlFileConfigLoader()
            # Load configuration
            logger.info("📄 Loading configuration using YamlFileConfigLoader")
            logger.info(f"🌍 Detected environment: {loader.environment}")
            
            self.config = loader.load()

                
            logger.info("✅ Configuration loaded successfully")
            logger.info(f"   App: {self.config.app.name} v{self.config.app.version}")
            
            # Log transport configuration
            #TODO: Load transport service automatically
            if self.config.app.transport and self.config.app.transport.kafka:
                logger.info(f"   Kafka: {self.config.app.transport.kafka.bootstrap_servers}")
            else:
                logger.warning("⚠️ No Kafka transport configuration found")
            
            # Log storage configuration
            storage_config = self.config.app.get_storage_config()
            enabled_backends = storage_config.get_enabled_backends()
            logger.info(f"   Storage backends: {enabled_backends}")
            
            logger.info(f"   Domains: {[d.name for d in self.config.domains]}")
            
            # Create Archive Service
            logger.info("🔧 Creating archive service...")
            archive_service = ArchiveService(self.config)
            logger.info("✅ Archive service created")
            
            # Create Kafka transport service
            logger.info("🔧 Creating Kafka transport service...")
            self.kafka_transport = KafkaTransportService(self.config, archive_service)
            logger.info("✅ Kafka transport service created")
            
            # Perform health check
            health = await self.kafka_transport.health_check()
            if health['healthy']:
                logger.info("✅ Kafka transport service health check passed")
                logger.info(f"   Producer ready: {health['details']['producer']}")
                logger.info(f"   Bootstrap servers: {health['details']['kafka_config']['bootstrap_servers']}")
            else:
                logger.warning("⚠️ Kafka transport service health check failed")
            
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
        logger.info("🚀 Starting Archive Generator Application...")
        logger.info("📡 Listening for archive requests via Kafka transport...")
        
        try:
            # Start the Kafka transport service (this will block until shutdown)
            transport_task = asyncio.create_task(self.kafka_transport.start())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            # Wait for either transport to finish or shutdown signal
            done, pending = await asyncio.wait(
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
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        # Register signal handlers
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, signal_handler)
        
        logger.info("📡 Signal handlers registered (SIGTERM, SIGINT)")
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        logger.info("🛑 Shutting down Archive Generator Application...")
        self.running = False
        self._shutdown_event.set()
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("🧹 Cleaning up resources...")
        
        if self.kafka_transport:
            await self.kafka_transport.stop()
            logger.info("✅ Kafka transport service stopped")
        
        logger.info("✅ Cleanup completed")

async def main():
    """Main entry point."""
    app = ArchiveGeneratorApp()
    logger.info("🎯 Starting Archive Generator Application")
    try:
        success = await app.start()
        if success:
            logger.info("👋 Archive Generator Application finished successfully")
        else:
            logger.error("❌ Archive Generator Application finished with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Application interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    print("🎯 Archive Generator - Event-Driven Archive Processing")
    print("")
    
    # Environment-based configuration system
    # Detection priority: ARCHIVE_ENV > Docker > Test (pytest) > development
    logger.info("=" * 50)
    logger.info("🎯 Starting Archive Generator Application")
    asyncio.run(main())
