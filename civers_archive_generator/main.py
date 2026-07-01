# main.py
import asyncio
import logging
import signal
import sys
from typing import Optional

from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services import TransportServiceInterface, KafkaTransportService, CliTransportService
from archive_services import ArchiveService

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, log_file='archive_generator.log', suppress_kafka_logs=True)

logger = get_logger(__name__)

class ArchiveGeneratorApp:
    """Main application using the modular transport service architecture."""
    
    def __init__(self, args: Optional[list[str]] = None):
        """Initialize the application."""
        self.config = None
        self.kafka_transport: Optional[TransportServiceInterface] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        self.args = args if args is not None else sys.argv[1:]
        
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
            
            # Log storage configuration
            storage_config = self.config.app.get_storage_config()
            enabled_backends = storage_config.get_enabled_backends()
            logger.info(f"   Storage backends: {enabled_backends}")
            
            logger.info(f"   Domains: {[d.name for d in self.config.domains]}")
            
            # Create Archive Service
            logger.info("🔧 Creating archive service...")
            archive_service = ArchiveService(self.config)
            logger.info("✅ Archive service created")
            
            # Determine which transport to load
            transport_config = self.config.app.transport
            is_cli = False
            for arg in self.args:
                if arg.startswith("--url") or arg == "--transport=cli" or (len(self.args) >= 2 and self.args[0] == "--transport" and self.args[1] == "cli"):
                    is_cli = True
                    break
            
            if is_cli or (transport_config and transport_config.is_transport_enabled("cli")):
                logger.info("🔧 Creating CLI transport service...")
                self.kafka_transport = CliTransportService(self.config, archive_service, args=self.args)
                logger.info("✅ CLI transport service created")
            elif transport_config and transport_config.is_transport_enabled("kafka"):
                # Log transport configuration
                if transport_config.kafka:
                    logger.info(f"   Kafka: {transport_config.kafka.bootstrap_servers}")
                
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
            else:
                logger.warning("⚠️ No supported transport service is enabled. App will run in idle state.")
                self.kafka_transport = None
            
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
        
        try:
            if self.kafka_transport:
                logger.info(f"📡 Listening via {self.kafka_transport.get_transport_info().get('type')} transport...")
                if self.kafka_transport.get_transport_info().get('type') == 'CLI':
                    # CLI is a single-shot task, run it directly in the foreground
                    await self.kafka_transport.start()
                else:
                    # Daemon transports run in the background
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
                    
                    # Check for exceptions in completed transport task to avoid unretrieved exception errors
                    if transport_task in done:
                        exc = transport_task.exception()
                        if exc:
                            raise exc
            else:
                logger.info("📡 Application running in idle mode (no transport active). Press Ctrl+C to stop.")
                await self._shutdown_event.wait()
            
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
            logger.info("✅ Transport service stopped")
        
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
