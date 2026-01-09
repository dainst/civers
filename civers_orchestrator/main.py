#!/usr/bin/env python3
"""Main entry point for CiVers Orchestrator.

This application coordinates the web archiving workflow by managing communication
between multiple microservices in the CiVers ecosystem using a transport-agnostic
architecture with configurable event-driven workflows.

Usage:
    # Run with default configuration
    uv run python main.py

    # Run with specific environment
    CONFIG_ENVIRONMENT=production uv run python main.py

    # Run with custom config directory
    uv run python main.py --config-dir /path/to/configs

    # Show version and exit
    uv run python main.py --version

    # Show help
    uv run python main.py --help
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path
import os
from typing import Optional

from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from orchestration_services.orchestrator_service import OrchestratorService
from transport_services.kafka.kafka_transport_service import KafkaTransportService

# Version
__version__ = "1.0.0"

# Logger (initialized after setup_logging is called)
logger = None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CiVers Orchestrator - Transport-agnostic workflow orchestration service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default configuration
  uv run python main.py

  # Run with specific environment
  CONFIG_ENVIRONMENT=production uv run python main.py

  # Run with custom config directory
  uv run python main.py --config-dir /path/to/configs

Environment Variables:
  CONFIG_ENVIRONMENT    Override environment detection (development, testing, docker, production)
  KAFKA_BOOTSTRAP_SERVERS    Override Kafka connection string
  LOG_LEVEL             Set logging level (DEBUG, INFO, WARNING, ERROR)

For more information, see: https://github.com/dainst/civers_orchestrator
        """
    )

    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Path to configuration directory (default: ./configs)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.getenv("LOG_LEVEL", "INFO").upper(),
        help="Set logging level (default: INFO, or LOG_LEVEL env var)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"CiVers Orchestrator v{__version__}",
    )

    return parser.parse_args()


class OrchestratorApp:
    """Main application class for the CiVers Orchestrator.
    
    This class encapsulates the application lifecycle including initialization,
    startup, background monitoring, and graceful shutdown.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the application.
        
        Args:
            config_dir: Optional path to configuration directory.
        """
        self.config_dir = config_dir
        self.config = None
        self.config_loader: Optional[YamlFileConfigLoader] = None
        self.orchestrator: Optional[OrchestratorService] = None
        self.transport: Optional[KafkaTransportService] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._transport_task = None
        self._monitoring_task = None

    async def initialize(self) -> bool:
        """Initialize application components.
        
        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            logger.info("🚀 Initializing Orchestrator Application...")

            # Load configuration
            logger.info("📁 Loading configuration...")
            self.config_loader = YamlFileConfigLoader(config_dir=self.config_dir)
            self.config = self.config_loader.load()

            logger.info("✅ Configuration loaded")
            logger.info(f"   Environment: {self.config.app.environment}")
            logger.info(f"   App Name: {self.config.app.name}")
            logger.info(f"   Version: {self.config.app.version}")
            logger.info(f"   Workflows: {len(self.config.workflows)} configured")
            logger.info(f"   Domains: {len(self.config.domains)} configured")

            # Initialize orchestrator (pure business logic - transport-agnostic)
            logger.info("🧠 Initializing orchestrator service...")
            self.orchestrator = OrchestratorService(self.config)
            logger.info("✅ Orchestrator initialized")

            # Initialize transport (Kafka)
            logger.info("📡 Initializing Kafka transport service...")
            self.transport = KafkaTransportService(self.config, self.orchestrator)
            logger.info("✅ Kafka transport initialized")
            logger.info(f"   Bootstrap servers: {self.config.transport.kafka.bootstrap_servers}")
            logger.info(f"   Consumer group: {self.config.transport.kafka.consumer.group_id}")
            logger.info(f"   Component mappings: {len(self.config.transport.kafka.component_mappings)}")

            # Perform health check
            health = await self.transport.health_check()
            if health.get('healthy', False):
                logger.info("✅ Kafka transport health check passed")
            else:
                logger.warning("⚠️ Kafka transport health check failed (service may still start)")

            logger.info("🎉 Application initialized successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize application: {e}", exc_info=True)
            return False

    async def start(self) -> bool:
        """Start the application.
        
        Returns:
            True if started successfully, False otherwise.
        """
        if not await self.initialize():
            logger.error("❌ Application initialization failed")
            return False

        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

        self.running = True
        logger.info("=" * 80)
        logger.info("✅ Orchestrator is running and ready to process requests")
        logger.info("   Press Ctrl+C to stop")
        logger.info("=" * 80)

        try:
            # Start transport service in background
            self._transport_task = asyncio.create_task(self.transport.start())

            # Start background monitoring task (timeouts and cleanup)
            self._monitoring_task = asyncio.create_task(
                self._background_monitoring(interval=30)
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            logger.info("=" * 80)
            logger.info("✅ Application stopped successfully")
            logger.info("=" * 80)
            return True

        except Exception as e:
            logger.error(f"❌ Application error: {e}", exc_info=True)
            return False
        finally:
            await self.cleanup()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"📡 Received signal {sig_name}, initiating shutdown...")
            asyncio.create_task(self.shutdown())

        # Register signal handlers
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, signal_handler)

        logger.info("📡 Signal handlers registered (SIGTERM, SIGINT)")

    async def _background_monitoring(self, interval: int = 60):
        """Background task for timeout monitoring and cleanup.
        
        Args:
            interval: Seconds between monitoring cycles.
        """
        logger.info(f"⏱️ Starting background monitoring task (interval: {interval}s)")

        while self.running:
            try:
                await asyncio.sleep(interval)
                
                if not self.running:
                    break

                # 1. Check for timeouts
                logger.debug("Checking for workflow timeouts...")
                timeout_transitions = self.orchestrator.check_all_timeouts()

                for transition in timeout_transitions:
                    logger.warning(
                        f"⏱️ Workflow {transition.workflow_instance.request_id} timed out "
                        f"at step {transition.failed_step}"
                    )
                    await self.transport._execute_transition(transition)

                # 2. Cleanup old workflows
                cleaned = self.orchestrator.cleanup_completed_workflows()
                if cleaned > 0:
                    logger.debug(f"🧹 Cleaned up {cleaned} old workflows")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background monitoring task: {e}")

        logger.info("⏱️ Background monitoring task stopped")

    async def shutdown(self):
        """Shutdown the application gracefully."""
        logger.info("🛑 Shutting down Orchestrator Application...")
        self.running = False
        self._shutdown_event.set()

    async def cleanup(self):
        """Clean up resources."""
        logger.info("🧹 Cleaning up resources...")

        # Stop transport service
        if self.transport:
            logger.info("⏸️ Stopping transport service...")
            await self.transport.stop()
            logger.info("✅ Transport service stopped")

        # Cancel transport task
        if self._transport_task:
            self._transport_task.cancel()
            try:
                await self._transport_task
            except asyncio.CancelledError:
                pass

        # Cancel monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ Cleanup completed")


async def main():
    """Main entry point."""
    global logger

    # Parse command line arguments
    args = parse_args()

    # Setup logging using centralized config
    setup_logging(level=args.log_level)

    # Initialize logger after setup
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info(f"CiVers Orchestrator v{__version__}")
    logger.info("Transport-Agnostic Workflow Orchestration Service")
    logger.info("=" * 80)

    app = OrchestratorApp(config_dir=args.config_dir)

    try:
        success = await app.start()
        if success:
            logger.info("👋 Orchestrator Application finished successfully")
        else:
            logger.error("❌ Orchestrator Application finished with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Application interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run application
    asyncio.run(main())
