# send_test_requests.py
import asyncio
import json
import logging
import argparse
from typing import List
from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.event_models import ArchiveRequestEvent
import os

from aiokafka import AIOKafkaProducer
from archive_services import ArchiveService

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class DirectRequestSender:
    """Utility to process archive requests directly using ArchiveService (bypassing Kafka)."""
    
    def __init__(self, environment: str = "development"):
        # Set environment variable for this loader instance
        original_env = os.getenv("CONFIG_ENVIRONMENT")
        os.environ["CONFIG_ENVIRONMENT"] = environment
        try:
            self.config = YamlFileConfigLoader().load()
        finally:
            # Restore original environment variable
            if original_env is not None:
                os.environ["CONFIG_ENVIRONMENT"] = original_env
            elif "CONFIG_ENVIRONMENT" in os.environ:
                del os.environ["CONFIG_ENVIRONMENT"]
        
        logger.info("🔧 Initializing ArchiveService for direct processing...")
        self.archive_service = ArchiveService(self.config)
        logger.info("✅ ArchiveService ready")

    async def send_requests(self, urls: List[str]):
        """Process archive requests directly."""
        logger.info(f"🚀 Processing {len(urls)} archive requests DIRECTLY (bypassing Kafka)...")
        
        for i, url in enumerate(urls, 1):
            request_id = f"direct-test-{i}"
            logger.info(f"📋 Processing request {i}: {url}")
            logger.info(f"   Request ID: {request_id}")
            
            try:
                result = await self.archive_service.create_archive(url, request_id)
                if result.get('success'):
                    logger.info(f"✅ SUCCESSFULLY archived {url}")
                    logger.info(f"   Storage ID: {result.get('storage_id', 'N/A')}")
                    logger.info(f"   Time: {result.get('processing_time_seconds', 0):.2f}s")
                else:
                    logger.error(f"❌ FAILED to archive {url}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Unexpected error processing {url}: {e}")
            
            logger.info("-" * 30)

    async def close(self):
        """No-op for direct sender cleanup."""
        pass

class TestRequestSender:
    """Utility to send test archive requests using aiokafka."""
    
    def __init__(self, environment: str = "development"):
        # Set environment variable for this loader instance
        original_env = os.getenv("CONFIG_ENVIRONMENT")
        os.environ["CONFIG_ENVIRONMENT"] = environment
        try:
            self.config = YamlFileConfigLoader().load()
        finally:
            # Restore original environment variable
            if original_env is not None:
                os.environ["CONFIG_ENVIRONMENT"] = original_env
            elif "CONFIG_ENVIRONMENT" in os.environ:
                del os.environ["CONFIG_ENVIRONMENT"]
        
        # Get Kafka configuration
        kafka_config = self.config.app.get_kafka_config()
        if not kafka_config:
            raise ValueError("Kafka configuration not found in transport settings")
        
        self.bootstrap_servers = kafka_config.bootstrap_servers
        self.topics = kafka_config.topics
        self.producer = None
    
    async def _ensure_producer(self):
        """Create and start the aiokafka producer if not already running."""
        if self.producer is None:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=1,
                request_timeout_ms=30000,
            )
            await self.producer.start()
    
    async def send_requests(self, urls: List[str]):
        """Send archive requests for the given URLs."""
        await self._ensure_producer()
        
        logger.info(f"📤 Sending {len(urls)} archive requests...")
        
        for i, url in enumerate(urls, 1):
            # Create request event
            request_event = ArchiveRequestEvent(
                url=url,
                priority=i,
                request_id=f"test-request-{i}",
            )
            
            logger.info(f"📤 Publishing archive request {i}: {url}")
            logger.info(f"   Request ID: {request_event.request_id}")
            
            # Publish to archive.requests so the running service processes it
            try:
                await self.producer.send_and_wait(
                    topic=self.topics['archive_requests'],
                    key=request_event.request_id,
                    value=request_event.model_dump()
                )
                logger.info(f"✅ Archive request {i} published")
            except Exception as e:
                logger.error(f"❌ Failed to publish archive request {i}: {e}")
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        logger.info("✅ All archive requests published")
    
    async def close(self):
        """Close the producer."""
        if self.producer:
            await self.producer.stop()

def get_default_urls() -> List[str]:
    """Get default test URLs if none are provided."""
    return [
        # Working URLs for testing
        "https://example.com/",
        "https://httpbin.org/get",
        # Problematic arachne URLs (network issues) - testing fixes
        "https://arachne.test.dainst.org/entity/1152996?fl=20&q=*&resultIndex=3",
        "https://arachne.test.dainst.org/entity/1215459?fl=20&q=*&resultIndex=8",
    ]

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Send test archive requests to the Archive Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default test URLs
  %(prog)s https://example.com                # Archive single URL
  %(prog)s https://example.com https://httpbin.org/get  # Archive multiple URLs
  %(prog)s --environment=testing https://example.com   # Use testing environment
        """
    )
    
    parser.add_argument(
        "urls",
        nargs="*",
        help="URLs to archive. If none provided, uses default test URLs"
    )
    
    parser.add_argument(
        "--environment", "-e",
        default="development",
        choices=["development", "testing", "docker", "production"],
        help="Configuration environment to use (default: development)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--direct", "-d",
        action="store_true",
        help="Process requests directly via ArchiveService (bypasses Kafka)"
    )
    
    return parser.parse_args()

async def main(urls: List[str], environment: str, direct: bool = False):
    """Send or process archive requests for the specified URLs."""
    if direct:
        sender = DirectRequestSender(environment=environment)
    else:
        sender = TestRequestSender(environment=environment)

    try:
        await sender.send_requests(urls)
    finally:
        await sender.close()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging level based on verbose flag
    if args.verbose:
        setup_logging(level=logging.DEBUG, suppress_kafka_logs=True)
        logger = get_logger(__name__)
    
    # Use provided URLs or default ones
    urls = args.urls if args.urls else get_default_urls()
    
    # Environment can be overridden by UV_LOG_LEVEL for backward compatibility
    environment = args.environment
    debug_mode = os.getenv("UV_LOG_LEVEL", "false").lower() == "debug"
    if debug_mode and environment == "development":
        logger.debug("Debug mode detected via UV_LOG_LEVEL. Switching to testing environment.")
        environment = "testing"
    
    logger.info("📤 Archive Request Sender")
    logger.info(f"Environment: {environment}")
    logger.info(f"URLs to archive: {len(urls)}")
    for i, url in enumerate(urls, 1):
        logger.info(f"  {i}. {url}")
    logger.info("=" * 50)
    
    asyncio.run(main(urls, environment, direct=args.direct))