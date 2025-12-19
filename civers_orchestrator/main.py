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


async def background_monitoring_task(
    orchestrator: OrchestratorService,
    transport: KafkaTransportService,
    interval: int = 60
):
    """Background task for timeout monitoring and cleanup."""
    logger.info(f"⏱️ Starting background monitoring task (interval: {interval}s)")

    while True:
        try:
            # 1. Check for timeouts
            logger.debug("Checking for workflow timeouts...")
            timeout_transitions = orchestrator.check_all_timeouts()

            for transition in timeout_transitions:
                logger.warning(
                    f"⏱️ Workflow {transition.workflow_instance.request_id} timed out "
                    f"at step {transition.failed_step}"
                )
                await transport._execute_transition(transition)

            # 2. Cleanup old workflows
            # logger.debug("Cleaning up old workflows...")
            orchestrator.cleanup_completed_workflows()

        except Exception as e:
            logger.error(f"Error in background monitoring task: {e}")

        await asyncio.sleep(interval)


async def main():
    """Main application entry point."""
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

    try:
        # Load configuration
        logger.info("📁 Loading configuration...")
        config_loader = YamlFileConfigLoader(config_dir=args.config_dir)
        config = config_loader.load()

        logger.info(f"✅ Configuration loaded")
        logger.info(f"   Environment: {config.app.environment}")
        logger.info(f"   App Name: {config.app.name}")
        logger.info(f"   Version: {config.app.version}")
        logger.info(f"   Workflows: {len(config.workflows)} configured")
        logger.info(f"   Domains: {len(config.domains)} configured")
        logger.info(f"   Config: {config}")
        # Initialize orchestrator (pure business logic - transport-agnostic)
        logger.info("🧠 Initializing orchestrator service...")
        orchestrator = OrchestratorService(config)
        logger.info(f"✅ Orchestrator initialized")

        # Initialize transport (Kafka)
        logger.info("🚀 Initializing Kafka transport service...")
        transport = KafkaTransportService(config, orchestrator)
        logger.info(f"✅ Kafka transport initialized")
        logger.info(f"   Bootstrap servers: {config.transport.kafka.bootstrap_servers}")
        logger.info(f"   Consumer group: {config.transport.kafka.consumer.group_id}")
        logger.info(f"   Component mappings: {len(config.transport.kafka.component_mappings)}")

        # Setup graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(sig, frame):
            """Handle shutdown signals gracefully."""
            sig_name = signal.Signals(sig).name
            logger.info(f"⚠️  Shutdown signal received: {sig_name}")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start transport service (begins consuming events)
        logger.info("🎬 Starting transport service...")
        logger.info("=" * 80)
        logger.info("✅ Orchestrator is running and ready to process requests")
        logger.info("   Press Ctrl+C to stop")
        logger.info("=" * 80)

        # Start transport in background
        transport_task = asyncio.create_task(transport.start())

        # Start background monitoring task (timeouts and cleanup)
        monitoring_task = asyncio.create_task(
            background_monitoring_task(orchestrator, transport, interval=30)
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Graceful shutdown
        logger.info("=" * 80)
        logger.info("🛑 Initiating graceful shutdown...")
        logger.info("=" * 80)

        # Stop transport service
        logger.info("⏸️  Stopping transport service...")
        await transport.stop()

        # Cancel transport task
        transport_task.cancel()
        try:
            await transport_task
        except asyncio.CancelledError:
            logger.info("✅ Transport service stopped")

        # Cancel monitoring task
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            logger.info("✅ Monitoring task stopped")

        logger.info("=" * 80)
        logger.info("👋 Shutdown complete. Goodbye!")
        logger.info("=" * 80)

    except KeyboardInterrupt:
        logger.info("⚠️  Keyboard interrupt received")
        sys.exit(0)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Application failed: {e}")
        logger.error("=" * 80)
        logger.exception("Stack trace:")
        sys.exit(1)


if __name__ == "__main__":
    # Run application
    asyncio.run(main())
