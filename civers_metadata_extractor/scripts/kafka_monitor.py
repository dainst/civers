# monitor_app.py
import asyncio
import json
import logging
from typing import Dict, Any
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from configs.yaml_file_loader_config import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.event_models import (
    MetadataExtractionStatusEvent, 
    MetadataExtractionCompletedEvent, 
    MetadataExtractionFailedEvent,
    MetadataQualityEvent
)

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class MetadataExtractionStatusMonitor:
    """Monitor that listens to metadata extraction status events and logs them."""
    
    def __init__(self, config_path: str = "app_config.yaml"):
        self.config = YamlFileConfigLoader(config_path).load()
        self.kafka_config = self.config.app.get_kafka_config()
        self.topics = self.kafka_config.topics
        self.consumer: AIOKafkaConsumer = None
        self.running = False
        self.stats = {
            'requests_processed': 0,
            'requests_completed': 0,
            'requests_failed': 0,
            'active_requests': set(),
            'quality_assessments': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0
        }
    
    async def _create_consumer(self):
        """Create async Kafka consumer for monitoring."""
        try:
            topics = [
                self.topics.get('metadata_status', 'metadata.status'),
                self.topics.get('metadata_extraction_completed', self.topics.get('metadata_extracted', 'metadata.extracted')), 
                self.topics['metadata_extraction_failed'],
                self.topics.get('metadata_quality', 'metadata.quality')  # Optional quality topic
            ]
            
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=f"{self.kafka_config.consumer_group}_monitor",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',  # Only new messages for monitoring
                enable_auto_commit=True,
                request_timeout_ms=30000,
            )
            
            # Start the async consumer
            await self.consumer.start()
            logger.info("✅ Monitor async Kafka consumer created and started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create monitor async Kafka consumer: {e}")
            raise
    
    async def start_monitoring(self):
        """Start monitoring metadata extraction events."""
        logger.info("📊 Starting Metadata Extraction Status Monitor...")
        
        # Create async consumer
        await self._create_consumer()
        self.running = True
        
        # Start consuming messages with native async iteration
        logger.info("📊 Monitoring for Kafka messages with native async iteration (Press Ctrl+C to stop)...")
        try:
            # Native async iteration over messages - no blocking!
            async for message in self.consumer:
                if not self.running:
                    logger.info("🛑 Stopping message monitoring")
                    break
                    
                try:
                    topic = message.topic
                    key = message.key
                    value = message.value
                    
                    if topic == self.topics.get('metadata_status', 'metadata.status'):
                        await self.handle_status_event(value, key, message.partition, message.offset)
                    elif topic == self.topics.get('metadata_extraction_completed', self.topics.get('metadata_extracted', 'metadata.extracted')):
                        await self.handle_completed_event(value, key, message.partition, message.offset)
                    elif topic == self.topics['metadata_extraction_failed']:
                        await self.handle_failed_event(value, key, message.partition, message.offset)
                    elif topic == self.topics.get('metadata_quality'):
                        await self.handle_quality_event(value, key, message.partition, message.offset)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message from {message.topic}: {e}")
                    
        except Exception as e:
            if self.running:
                logger.error(f"❌ Error in monitoring loop: {e}")
            raise
                        
        except KeyboardInterrupt:
            logger.info("👋 Monitor stopped by user")
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
        domain_used = event.get('domain_used', 'unknown')
        mappers_used = event.get('mappers_used', [])
        
        logger.info(f"✅ Metadata Extraction Completed - {request_id}")
        logger.info(f"   URL: {event.get('url')}")
        logger.info(f"   Domain: {domain_used}")
        logger.info(f"   Mappers: {mappers_used}")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        
        # Update statistics
        self.stats['requests_completed'] += 1
        self.stats['active_requests'].discard(request_id)
        self.stats['total_processing_time'] += processing_time
        
        # Calculate running average
        total_requests = self.stats['requests_completed'] + self.stats['requests_failed']
        if total_requests > 0:
            self.stats['average_processing_time'] = self.stats['total_processing_time'] / total_requests
        
        await self._print_stats()
    
    async def handle_failed_event(self, event: dict, key: str, partition: int, offset: int):
        """Handle failure events."""
        request_id = event.get('request_id')
        error_type = event.get('error_type', 'Unknown')
        failed_stage = event.get('failed_stage', 'unknown')
        
        logger.error(f"❌ Metadata Extraction Failed - {request_id}")
        logger.error(f"   URL: {event.get('url')}")
        logger.error(f"   Error Type: {error_type}")
        logger.error(f"   Failed Stage: {failed_stage}")
        logger.error(f"   Error: {event.get('error_message')}")
        
        self.stats['requests_failed'] += 1
        self.stats['active_requests'].discard(request_id)
        
        await self._print_stats()
    
    async def handle_quality_event(self, event: dict, key: str, partition: int, offset: int):
        """Handle quality assessment events."""
        request_id = event.get('request_id')
        quality_score = event.get('quality_score', 0.0)
        completeness_score = event.get('completeness_score', 0.0)
        missing_fields = event.get('missing_fields', [])
        
        logger.info(f"🎯 Quality Assessment - {request_id}")
        logger.info(f"   Overall Quality: {quality_score:.2f}")
        logger.info(f"   Completeness: {completeness_score:.2f}")
        if missing_fields:
            logger.info(f"   Missing Fields: {missing_fields}")
        
        self.stats['quality_assessments'] += 1
        
        await self._print_stats()
    
    async def _print_stats(self):
        """Print current statistics."""
        active_count = len(self.stats['active_requests'])
        total_processed = self.stats['requests_completed'] + self.stats['requests_failed']
        avg_time = self.stats['average_processing_time']
        
        logger.info(f"📈 Stats: Active={active_count}, Completed={self.stats['requests_completed']}, "
                   f"Failed={self.stats['requests_failed']}, Total={total_processed}, "
                   f"Quality={self.stats['quality_assessments']}, Avg Time={avg_time:.2f}s")
    
    async def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("✅ Monitor async Kafka consumer stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping monitor async Kafka consumer: {e}")

async def async_main(config_path: str = "app_config.yaml"):
    """Run the status monitor asynchronously."""
    monitor = MetadataExtractionStatusMonitor(config_path=config_path)
    logger.info("📊 Initializing Metadata Extraction Status Monitor...")
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("👋 Monitor stopped by user")
    finally:
        await monitor.stop()

def main():
    """Synchronous wrapper for script entry point."""
    print("📊 Metadata Extraction Status Monitor")
    config_path = "app_config.yaml"
    # check if debug mode is enabled
    import os
    debug_mode = os.getenv("UV_LOG_LEVEL", "false").lower() == "debug"
    if debug_mode:
        logger.debug("Debug mode is enabled. Using test configuration.")
        config_path = "tests/integration/test_app_config.yaml"
    else:
        logger.info("Debug mode is disabled. Using default configuration.")
    logger.info(f"Using configuration file: {config_path}")
    logger.info("=" * 50)
    asyncio.run(async_main(config_path))

if __name__ == "__main__":
    main()
