"""
Async Kafka Transport Service for CiVers Archive Generator.

This service handles archive requests via Kafka using asynchronous messaging
(aiokafka). It coordinates between the Kafka connection manager, the event
publisher, and the core archive service.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable

from configs.models import ConfigDataModel
from archive_services.archive_service_interface import ArchiveServiceInterface
from transport_services.transport_service_interface import TransportServiceInterface
from .event_models import (
    ArchiveRequestEvent,
    ArchiveStatusEvent,
    ArchiveCompletedEvent,
    ArchiveFailedEvent
)
from .kafka_connection_manager import KafkaConnectionManager
from .event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class KafkaTransportService(TransportServiceInterface):
    """
    Kafka transport service using aiokafka for async coordination.
    """
    
    def __init__(self, config: ConfigDataModel, archive_service: ArchiveServiceInterface):
        self.config = config
        self.archive_service = archive_service
        
        # Get Kafka configuration
        self.kafka_config = config.app.get_kafka_config()
        if not self.kafka_config:
            raise ValueError("Kafka configuration not found in transport settings")
        
        self.topics = self.kafka_config.topics
        self.running = False
        self._requests_processed = 0
        self.event_handlers: Dict[str, Callable] = {}
        
        # Initialize sub-components
        self.connection_manager = KafkaConnectionManager(self.kafka_config)
        self.event_publisher = EventPublisher(self.connection_manager, self.topics)

    def register_handler(self, topic: str, handler: Callable):
        """Register an event handler for a specific topic."""
        self.event_handlers[topic] = handler
        logger.info(f"✅ Registered handler for topic: {topic}")

    async def start(self):
        """Start the async Kafka transport service."""
        try:
            logger.info("🚀 Starting Async Kafka transport service")
            
            # Setup producer
            await self.connection_manager.setup_producer()
            
            # Register default topic handlers
            archive_request_topic = self.topics.get('archive_requests')
            if archive_request_topic:
                self.register_handler(archive_request_topic, self._handle_archive_request)
            
            # Setup consumer
            topics_to_consume = list(self.event_handlers.keys())
            if topics_to_consume:
                await self.connection_manager.setup_consumer(topics_to_consume)
            else:
                logger.warning("⚠️ No topics registered for consumption")
            
            self.running = True
            
            # Start the main consumption loop
            if self.connection_manager.consumer:
                await self._consume_loop()
                
        except Exception as e:
            logger.error(f"❌ Failed to start Kafka transport service: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the service gracefully."""
        self.running = False
        logger.info("🛑 Stopping Kafka transport service...")
        await self.connection_manager.cleanup()
        logger.info("✅ Kafka transport service stopped")

    async def _consume_loop(self):
        """Main async consumption loop."""
        logger.info("📡 Starting async Kafka consumption loop")
        try:
            async for msg in self.connection_manager.consumer:
                if not self.running:
                    break
                
                try:
                    await self._process_message(msg)
                except Exception as e:
                    logger.error(f"❌ Error processing Kafka message: {e}", exc_info=True)
                    
        except Exception as e:
            if self.running:
                logger.error(f"❌ Kafka consumption loop error: {e}")
                # Allow some time before potential restart or exit
                await asyncio.sleep(1)

    async def _process_message(self, message):
        """Process a message from the consumer."""
        topic = message.topic
        message_data = message.value
        
        if message_data is None:
            logger.warning(f"⚠️ Received empty message on topic {topic}")
            return
            
        handler = self.event_handlers.get(topic)
        if handler:
            await handler(message, message_data)
        else:
            logger.debug(f"ℹ️ No handler for topic {topic}")

    async def _handle_archive_request(self, message, message_data: Dict[str, Any]):
        """Handle incoming archive requests."""
        try:
            # Parse request event
            event = ArchiveRequestEvent(**message_data)
            request_id = event.request_id
            url = event.url
            priority = event.priority
            
            logger.info(f"🚀 Processing archive request: {request_id} for {url}")
            self._requests_processed += 1
            
            # 1. Send processing status
            await self.event_publisher.publish_status_update(ArchiveStatusEvent(
                request_id=request_id,
                url=url,
                status="processing",
                message=f"Archive generation started for {url}"
            ))
            
            # 2. Call the core archive service
            result = await self.archive_service.create_archive(url, request_id, priority)
            
            if result.get('success'):
                # Handle successful result
                # Extract snapshot_id if present
                snapshot_id = self._extract_snapshot_id(result)
                
                # 3. Publish completion event
                completion_event = ArchiveCompletedEvent(
                    request_id=request_id,
                    url=url,
                    archive_path=result['archive_path'],
                    artifacts_created=result['domain_config']['artifacts'],
                    processing_time_seconds=result['processing_time_seconds'],
                    snapshot_id=snapshot_id
                )
                await self.event_publisher.publish_archive_completed(completion_event)
                
                # 4. Final status update
                await self.event_publisher.publish_status_update(ArchiveStatusEvent(
                    request_id=request_id,
                    url=url,
                    status="completed",
                    message=f"Archive completed in {result['processing_time_seconds']:.1f}s"
                ))
                logger.info(f"✅ Archive {request_id} finished")
                
            else:
                # Handle failure
                error_msg = result.get('error', 'Unknown error')
                await self.event_publisher.publish_archive_failed(ArchiveFailedEvent(
                    request_id=request_id,
                    url=url,
                    error_message=error_msg
                ))
                
                await self.event_publisher.publish_status_update(ArchiveStatusEvent(
                    request_id=request_id,
                    url=url,
                    status="failed",
                    message=f"Archive failed: {error_msg}"
                ))
                logger.error(f"❌ Archive {request_id} failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ Critical error handling archive request: {e}", exc_info=True)

    def _extract_snapshot_id(self, result: Dict[str, Any]) -> Optional[str]:
        """Helper to extract snapshot ID from complex nested results."""
        try:
            storage_result = result.get('storage_result', {})
            artifacts_result = storage_result.get('artifacts_storage_result')
            if artifacts_result and hasattr(artifacts_result, 'results'):
                for res in artifacts_result.results:
                    if getattr(res, 'storage_type', None) == 'civers_rest_api' and getattr(res, 'success', False):
                        return getattr(res, 'storage_location', None)
            return None
        except Exception:
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Check health of Kafka transport service."""
        try:
            status = self.connection_manager.get_connection_status() if hasattr(self.connection_manager, 'get_connection_status') else {}
            is_healthy = self.connection_manager.producer is not None and self.running
            
            return {
                "healthy": is_healthy,
                "service_name": "KafkaTransportService",
                "details": {
                    "running": self.running,
                    "requests_processed": self._requests_processed,
                    "producer": "ready" if self.connection_manager.producer else "missing",
                    "consumer": "ready" if self.connection_manager.consumer else "missing"
                }
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def send_response(self, destination: str, message: Dict[str, Any], **kwargs) -> bool:
        """Generic response sender."""
        try:
            if not self.connection_manager.producer:
                return False
            await self.connection_manager.producer.send(destination, value=message, key=kwargs.get('key'))
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send response: {e}")
            return False

    def get_transport_info(self) -> Dict[str, Any]:
        """Info about the transport."""
        return {
            "type": "AsyncKafka",
            "bootstrap_servers": self.kafka_config.bootstrap_servers,
            "consumer_group": self.kafka_config.consumer_group
        }
