# monitor_app.py
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.event_models import ArchiveStatusEvent, ArchiveCompletedEvent, ArchiveFailedEvent

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class ArchiveStatusMonitor:
    """Monitor that listens to status events and logs them."""
    
    def __init__(self, environment: str = "development"):
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
        
        self.kafka_config = self.config.app.get_kafka_config()
        self.topics = self.kafka_config.topics
        self.consumer = None
        self.running = False
        self.stats = {
            'requests_processed': 0,
            'requests_completed': 0,
            'requests_failed': 0,
            'active_requests': set()
        }
    
    def _create_consumer(self):
        """Create Kafka consumer for monitoring."""
        try:
            topics = [
                self.topics['archive_status'],
                self.topics['archive_completed'], 
                self.topics['archive_failed']
            ]
            
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=f"{self.kafka_config.consumer_group}_monitor",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',  # Only new messages for monitoring
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=30000
            )
            logger.info("✅ Monitor Kafka consumer created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create monitor Kafka consumer: {e}")
            raise
    
    async def start_monitoring(self):
        """Start monitoring archive events."""
        logger.info("📊 Starting Archive Status Monitor...")
        
        # Create consumer
        self._create_consumer()
        self.running = True
        
        # Start consuming messages
        try:
            for message in self.consumer:
                if not self.running:
                    break
                    
                try:
                    topic = message.topic
                    key = message.key
                    value = message.value
                    
                    if topic == self.topics['archive_status']:
                        await self.handle_status_event(value, key, message.partition, message.offset)
                    elif topic == self.topics['archive_completed']:
                        await self.handle_completed_event(value, key, message.partition, message.offset)
                    elif topic == self.topics['archive_failed']:
                        await self.handle_failed_event(value, key, message.partition, message.offset)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message from {message.topic}: {e}")
                    
        except KeyboardInterrupt:
            logger.info("👋 Monitor stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in monitoring loop: {e}")
        finally:
            self.stop()
    
    async def handle_status_event(self, event: dict, key: str, partition: int, offset: int):
        """Handle status update events."""
        request_id = event.get('request_id')
        status = event.get('status')
        message = event.get('message')
        
        logger.info(f"📊 Status Update - {request_id}: {status}")
        if message:
            logger.info(f"   Message: {message}")
        
        # Track active requests
        if status == "processing":
            self.stats['active_requests'].add(request_id)
        elif status in ["completed", "failed"]:
            self.stats['active_requests'].discard(request_id)
        
        await self._print_stats()
    
    async def handle_completed_event(self, event: dict, key: str, partition: int, offset: int):
        """Handle completion events."""
        request_id = event.get('request_id')
        processing_time = event.get('processing_time_seconds', 0)
        
        logger.info(f"✅ Archive Completed - {request_id}")
        logger.info(f"   URL: {event.get('url')}")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Artifacts: {event.get('artifacts_created', [])}")
        
        self.stats['requests_completed'] += 1
        self.stats['active_requests'].discard(request_id)
        
        await self._print_stats()
    
    async def handle_failed_event(self, event: dict, key: str, partition: int, offset: int):
        """Handle failure events."""
        request_id = event.get('request_id')
        
        logger.error(f"❌ Archive Failed - {request_id}")
        logger.error(f"   URL: {event.get('url')}")
        logger.error(f"   Error: {event.get('error_message')}")
        
        self.stats['requests_failed'] += 1
        self.stats['active_requests'].discard(request_id)
        
        await self._print_stats()
    
    async def _print_stats(self):
        """Print current statistics."""
        active_count = len(self.stats['active_requests'])
        total_processed = self.stats['requests_completed'] + self.stats['requests_failed']
       
        logger.info(f"📈 Stats: Active={active_count}, Completed={self.stats['requests_completed']}, Failed={self.stats['requests_failed']}, Total={total_processed}")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("✅ Monitor Kafka consumer closed")
            except Exception as e:
                logger.error(f"❌ Error closing monitor Kafka consumer: {e}")

async def main(environment: str = "development"):
    """Run the status monitor."""
    monitor = ArchiveStatusMonitor(environment=environment)
    logger.info("📊 Initializing Archive Status Monitor...")
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("👋 Monitor stopped by user")
    finally:
        monitor.stop()

if __name__ == "__main__":
    print("📊 Archive Status Monitor")
    environment = "development"
    # check if debug mode is enabled
    import os
    debug_mode = os.getenv("UV_LOG_LEVEL", "false").lower() == "debug"
    if debug_mode:
        logger.debug("Debug mode is enabled. Using testing environment.")
        environment = "testing"
    else:
        logger.info("Debug mode is disabled. Using development environment.")
    logger.info(f"Using environment: {environment}")
    logger.info("=" * 50)
    asyncio.run(main(environment))
