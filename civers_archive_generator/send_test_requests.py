# send_test_requests.py
import asyncio
import logging
import sys
import argparse
from typing import List
from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.event_models import ArchiveRequestEvent
import os

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class TestRequestSender:
    """Utility to send test archive requests."""
    
    def __init__(self, environment: str = "development"):
        import json
        from kafka import KafkaProducer
        # Set environment variable for this loader instance
        original_env = os.getenv("ARCHIVE_ENV")
        os.environ["ARCHIVE_ENV"] = environment
        try:
            self.config = YamlFileConfigLoader().load()
        finally:
            # Restore original environment variable
            if original_env is not None:
                os.environ["ARCHIVE_ENV"] = original_env
            elif "ARCHIVE_ENV" in os.environ:
                del os.environ["ARCHIVE_ENV"]
        
        # Get Kafka configuration
        kafka_config = self.config.app.get_kafka_config()
        if not kafka_config:
            raise ValueError("Kafka configuration not found in transport settings")
        
        # Create producer only (no consumer to avoid interfering with main app)
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_config.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks=1,
            retries=3,
            max_in_flight_requests_per_connection=1,
            request_timeout_ms=30000,
            api_version_auto_timeout_ms=30000
        )
        self.topics = kafka_config.topics
    
    async def send_requests(self, urls: List[str]):
        """Send archive requests for the given URLs."""
        
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
                future = self.producer.send(
                    topic=self.topics['archive_requests'],
                    key=request_event.request_id,
                    value=request_event.model_dump()
                )
                future.get(timeout=10)
                logger.info(f"✅ Archive request {i} published")
            except Exception as e:
                logger.error(f"❌ Failed to publish archive request {i}: {e}")
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        logger.info("✅ All archive requests published")
    
    async def close(self):
        """Close the producer."""
        if self.producer:
            self.producer.close()

def get_default_urls() -> List[str]:
    """Get default test URLs if none are provided."""
    return [
        # Working URLs for testing
        "https://example.com/",
        "https://httpbin.org/get",
        # Problematic arachne URLs (network issues) - testing fixes
        "https://arachne.dainst.org/entity/1152996?fl=20&q=*&resultIndex=3",
        "https://arachne.dainst.org/entity/1215459?fl=20&q=*&resultIndex=8",
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
    
    return parser.parse_args()

async def main(urls: List[str], environment: str):
    """Send archive requests for the specified URLs."""
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
    
    asyncio.run(main(urls, environment))