# transport_services/kafka_transport_service.py
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from configs.models import ConfigDataModel
from archive_services.archive_service_interface import ArchiveServiceInterface
from transport_services.transport_service_interface import TransportServiceInterface
from .event_models import (
    ArchiveRequestEvent,
    ArchiveStatusEvent, 
    ArchiveCompletedEvent, 
    ArchiveFailedEvent
)

logger = logging.getLogger(__name__)

class KafkaTransportService(TransportServiceInterface):
    """
    Kafka transport service that handles archive requests via Kafka messaging.
    
    This service:
    1. Consumes archive requests from Kafka topics
    2. Delegates archive creation to injected ArchiveServiceInterface
    3. Publishes status updates and completion/failure events
    
    Uses dependency injection for better testability and loose coupling.
    """
    
    def __init__(self, config: ConfigDataModel, archive_service: ArchiveServiceInterface):
        self.config = config
        self.archive_service = archive_service
        
        # Get Kafka configuration from transport settings
        self.kafka_config = config.app.get_kafka_config()
        if not self.kafka_config:
            raise ValueError("Kafka configuration not found in transport settings")
        
        self.topics = self.kafka_config.topics
        self.running = False
        
        # Kafka components
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
        self.event_handlers: Dict[str, Callable] = {}
        
        # Initialize producer
        self._setup_producer()

    @staticmethod
    def _safe_json_deserializer(m: Optional[bytes]):
        """Decode bytes to JSON with resilience to malformed payloads.
        - Returns dict when JSON parsed
        - Returns None when not parseable, logging a warning
        """
        if m is None:
            return None
        try:
            s = m.decode('utf-8', errors='ignore')
        except Exception:
            logger.warning("⚠️ Failed to decode Kafka message bytes; skipping")
            return None
        # Fast path
        try:
            return json.loads(s)
        except Exception:
            # Try to extract JSON object substring
            start = s.find('{')
            end = s.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = s[start:end+1]
                try:
                    logger.debug("Attempting to parse JSON from substring of message value")
                    return json.loads(candidate)
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse JSON from candidate substring: {e}. Raw snippet: {s[:200]}")
                    return None
            logger.warning(f"⚠️ Received non-JSON Kafka message; skipping. Raw snippet: {s[:200]}")
            return None
    
    def _setup_producer(self):
        """Initialize Kafka producer for publishing events."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=1,  # Wait for leader acknowledgment
                retries=3,  # Retry failed sends
                max_in_flight_requests_per_connection=1,  # Ensure ordering
                request_timeout_ms=30000,  # Longer timeout for Docker
                api_version_auto_timeout_ms=30000
            )
            logger.info("✅ Kafka producer initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka producer: {e}")
            raise
    
    def _setup_consumer(self):
        """Initialize Kafka consumer for consuming archive requests."""
        try:
            topics_to_consume = list(self.event_handlers.keys())
            if not topics_to_consume:
                logger.warning("⚠️ No topics registered for consumption")
                return
            
            self.consumer = KafkaConsumer(
                *topics_to_consume,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=self.kafka_config.consumer_group,
                value_deserializer=self._safe_json_deserializer,
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='earliest',  # Start from beginning for testing
                enable_auto_commit=True,
                consumer_timeout_ms=1000,  # 1 second timeout for polling
                request_timeout_ms=30000,  # 30 second timeout for Docker
                api_version_auto_timeout_ms=30000
            )
            
            logger.info(f"✅ Kafka consumer initialized for topics: {topics_to_consume}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka consumer: {e}")
            raise
    
    def register_handler(self, topic: str, handler: Callable):
        """Register an event handler for a specific topic."""
        self.event_handlers[topic] = handler
        logger.info(f"✅ Registered handler for topic: {topic}")
    
    async def start(self):
        """Start the Kafka transport service."""
        try:
            logger.info("🚀 Starting Kafka transport service")
            
            # Register default handler for archive requests
            if self.topics.get('archive_requests'):
                self.register_handler(
                    self.topics['archive_requests'], 
                    self._handle_archive_request
                )
            
            # Setup consumer
            self._setup_consumer()
            
            if not self.consumer:
                raise ValueError("Failed to setup Kafka consumer")
            
            self.running = True
            
            # Start consuming messages
            await self._start_consuming()
            
        except Exception as e:
            logger.error(f"❌ Failed to start Kafka transport service: {e}")
            await self.stop()
            raise
    
    async def _start_consuming(self):
        """Start consuming messages from Kafka."""
        logger.info("📡 Starting to consume Kafka messages")
        
        while self.running:
            try:
                # Poll for messages with timeout
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process all messages in the batch
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            await self._process_kafka_message(message)
                        except Exception as e:
                            logger.error(f"❌ Error processing Kafka message: {e}", exc_info=True)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Kafka polling error: {e}")
                    await asyncio.sleep(1)
    
    async def _process_kafka_message(self, message):
        """Process a single Kafka message."""
        try:
            topic = message.topic
            request_id = message.key or "unknown"
            message_data = message.value
            
            if message_data is None:
                logger.warning("⚠️ Received empty or malformed Kafka message; skipping")
                return
            
            logger.info(f"📥 Kafka message received from topic {topic}: {request_id}")
            logger.debug(f"   Message data: {message_data}")
            
            # Get handler for this topic
            handler = self.event_handlers.get(topic)
            if not handler:
                logger.warning(f"⚠️ No handler registered for topic: {topic}")
                return
            
            # Call the handler
            await handler(message, message_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to process Kafka message: {e}", exc_info=True)
    
    async def _handle_archive_request(self, message, message_data: Dict[str, Any]):
        """
        Handle archive request messages.
        
        Delegates archive creation to the injected ArchiveServiceInterface
        while handling all Kafka-specific messaging concerns.
        """
        try:
            # Parse the archive request event
            archive_request = ArchiveRequestEvent(**message_data)
            request_id = archive_request.request_id
            url = archive_request.url
            priority = getattr(archive_request, 'priority', 1)
            
            logger.info(f"🚀 Processing archive request: {request_id} for {url}")
            
            # Send initial processing status
            await self._send_status_update(
                request_id=request_id,
                status="processing",
                message=f"Started processing archive for {url}",
                url=url
            )
            
            # Use ArchiveService for core business logic
            result = await self.archive_service.create_archive(url, request_id, priority)
            
            if result['success']:
                # Extract snapshot_id from storage result if available
                # The storage_result contains artifacts_storage_result with backend results
                snapshot_id = None
                storage_result = result.get('storage_result', {})
                artifacts_result = storage_result.get('artifacts_storage_result')
                if artifacts_result:
                    # Find civers_rest_api backend result which has the snapshot_id
                    for backend_result in artifacts_result.results:
                        if backend_result.storage_type == 'civers_rest_api' and backend_result.success:
                            snapshot_id = backend_result.storage_location
                            break
                
                # Send completion event
                completion_event = ArchiveCompletedEvent(
                    request_id=request_id,
                    url=url,
                    archive_path=result['archive_path'],
                    artifacts_created=result['domain_config']['artifacts'],
                    processing_time_seconds=result['processing_time_seconds'],
                    snapshot_id=snapshot_id
                )
                
                success = self._publish_archive_completed(completion_event)
                if success:
                    logger.info(f"✅ Archive completed for request {request_id} in {result['processing_time_seconds']:.2f}s")
                
                # Final status update
                await self._send_status_update(
                    request_id=request_id,
                    status="completed",
                    message=f"Archive generation completed successfully in {result['processing_time_seconds']:.1f}s",
                    url=url
                )
                
            else:
                # Send failure event
                failure_event = ArchiveFailedEvent(
                    request_id=request_id,
                    url=url,
                    error_message=result['error']
                )
                
                self._publish_archive_failed(failure_event)
                
                # Send failure status
                await self._send_status_update(
                    request_id=request_id,
                    status="failed",
                    message=f"Archive generation failed: {result['error']}",
                    url=url
                )
                
                logger.error(f"❌ Archive request failed: {request_id} - {result['error']}")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Archive request processing failed: {error_msg}", exc_info=True)
            
            # Send failure event and status for unexpected errors
            try:
                request_id = message_data.get('request_id', 'unknown')
                url = message_data.get('url', 'unknown')
                
                failure_event = ArchiveFailedEvent(
                    request_id=request_id,
                    url=url,
                    error_message=error_msg
                )
                
                self._publish_archive_failed(failure_event)
                
                await self._send_status_update(
                    request_id=request_id,
                    status="failed",
                    message=f"Archive processing failed: {error_msg}",
                    url=url
                )
                
            except Exception as nested_e:
                logger.error(f"❌ Failed to send failure notifications: {nested_e}")
    
    async def _send_status_update(self, request_id: str, status: str, message: str, url: str):
        """Send a status update event to Kafka."""
        try:
            status_event = ArchiveStatusEvent(
                request_id=request_id,
                status=status,
                message=message,
                url=url
            )
            
            success = self._publish_status_update(status_event)
            if success:
                logger.debug(f"📊 Status update sent: {status} - {message}")
            else:
                logger.warning(f"⚠️ Failed to send status update for {request_id}")
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to create/send status update: {e}")
    
    def _publish_status_update(self, event: ArchiveStatusEvent) -> bool:
        """Publish a status update event to Kafka."""
        return self._publish_event(
            topic=self.topics['archive_status'],
            key=event.request_id,
            event_data=event.model_dump()
        )
    
    def _publish_archive_completed(self, event: ArchiveCompletedEvent) -> bool:
        """Publish an archive completion event to Kafka."""
        return self._publish_event(
            topic=self.topics['archive_completed'],
            key=event.request_id,
            event_data=event.model_dump()
        )
    
    def _publish_archive_failed(self, event: ArchiveFailedEvent) -> bool:
        """Publish an archive failure event to Kafka."""
        return self._publish_event(
            topic=self.topics['archive_failed'],
            key=event.request_id,
            event_data=event.model_dump()
        )
    
    def publish_archive_request(self, event: ArchiveRequestEvent) -> bool:
        """Publish an archive request event to Kafka."""
        return self._publish_event(
            topic=self.topics['archive_requests'],
            key=event.request_id,
            event_data=event.model_dump()
        )
    
    def _publish_event(self, topic: str, key: str, event_data: Dict[str, Any]) -> bool:
        """Publish an event to a Kafka topic."""
        try:
            if not self.producer:
                logger.error("❌ Kafka producer not initialized")
                return False
            
            # Send the message
            future = self.producer.send(
                topic=topic,
                key=key,
                value=event_data
            )
            
            # Wait for acknowledgment (with timeout)
            future.get(timeout=10)
            
            logger.debug(f"📤 Event published to {topic}: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False
    
    async def stop(self):
        """Stop the Kafka transport service and cleanup resources."""
        logger.info("🛑 Stopping Kafka transport service")
        self.running = False
        
        try:
            if self.consumer:
                self.consumer.close()
                logger.info("✅ Kafka consumer closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing Kafka consumer: {e}")
        
        try:
            if self.producer:
                self.producer.close()
                logger.info("✅ Kafka producer closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing Kafka producer: {e}")
        
        logger.info("✅ Kafka transport service stopped")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the Kafka transport service."""
        try:
            health_status = {
                'service': 'kafka_transport',
                'running': self.running,
                'producer_ready': self.producer is not None,
                'consumer_ready': self.consumer is not None,
                'registered_topics': list(self.event_handlers.keys()),
                'kafka_config': {
                    'bootstrap_servers': self.kafka_config.bootstrap_servers,
                    'consumer_group': self.kafka_config.consumer_group,
                    'topics': self.topics
                }
            }
            
            return {
                'healthy': self.producer is not None,
                'running': self.running,
                'details': health_status
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    async def send_response(self, destination: str, message: Dict[str, Any], **kwargs) -> bool:
        """
        Send a response message to a Kafka topic.
        
        Args:
            destination: Kafka topic name
            message: The message to send
            **kwargs: Additional options like 'key'
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            key = kwargs.get('key', None)
            return self._publish_event(destination, key, message)
        except Exception as e:
            logger.error(f"❌ Failed to send response to {destination}: {e}")
            return False
    
    def get_transport_info(self) -> Dict[str, Any]:
        """
        Get information about the Kafka transport service configuration.
        
        Returns:
            Dict containing transport service information and capabilities
        """
        return {
            'transport_type': 'KafkaTransportService',
            'kafka_config': {
                'bootstrap_servers': self.kafka_config.bootstrap_servers,
                'consumer_group': self.kafka_config.consumer_group,
                'topics': self.topics
            },
            'status': {
                'running': self.running,
                'producer_ready': self.producer is not None,
                'consumer_ready': self.consumer is not None,
                'registered_handlers': len(self.event_handlers)
            },
            'capabilities': {
                'async_processing': True,
                'event_driven': True,
                'scalable': True,
                'persistent_messaging': True
            },
            'supported_events': [
                'ArchiveRequestEvent',
                'ArchiveStatusEvent', 
                'ArchiveCompletedEvent',
                'ArchiveFailedEvent'
            ]
        }
