# transport_services/kafka_transport_service.py
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone

from configs.models import ConfigDataModel
from .kafka_connection_manager import KafkaConnectionManager
from .event_publisher import EventPublisher
from metadata_extraction_services.metadata_extraction_service_interface import MetadataExtractionServiceInterface
from metadata_extraction_services.extraction_result import ExtractionResult
from transport_services.transport_service_interface import TransportServiceInterface
from .event_models import (
    MetadataExtractionRequestEvent,
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent,
)

logger = logging.getLogger(__name__)

class KafkaTransportService(TransportServiceInterface):
    """
    Kafka transport service that handles metadata extraction requests via Kafka messaging.
    
    This service:
    1. Consumes metadata extraction requests from Kafka topics
    2. Downloads HTML content if document_url is provided
    3. Delegates metadata extraction to injected MetadataExtractionServiceInterface
    4. Publishes completion/failure events directly
    
    Uses dependency injection for better testability and loose coupling.
    All logic is handled directly in this service without extra abstraction layers.
    """
    
    def __init__(self, config: ConfigDataModel, metadata_service: MetadataExtractionServiceInterface):
        self.config = config
        self.metadata_service = metadata_service
        
        # Get Kafka configuration from transport settings
        self.kafka_config = config.app.get_kafka_config()
        if not self.kafka_config:
            raise ValueError("Kafka configuration not found in transport settings")
        
        self.topics = self.kafka_config.topics
        self.running = False
        self.event_handlers: Dict[str, Callable] = {}
        
        # Initialize components
        self.connection_manager = KafkaConnectionManager(self.kafka_config)
        self.event_publisher = EventPublisher(self.connection_manager, self.topics)
        
        # Simple request counter
        self._requests_processed = 0
    
    
    def register_handler(self, topic: str, handler: Callable):
        """Register an event handler for a specific topic."""
        self.event_handlers[topic] = handler
        logger.info(f"✅ Registered handler for topic: {topic}")
    
    async def start(self):
        """Start the Kafka transport service."""
        try:
            logger.info("🚀 Starting Kafka transport service")
            
            # Register default handler for metadata extraction requests
            # Check both internal and shared config topic keys
            request_topic = self.topics.get('metadata_extraction_requests') or self.topics.get('metadata_requests')
            if request_topic:
                self.register_handler(
                    request_topic, 
                    self._handle_metadata_extraction_request
                )
            else:
                logger.warning("⚠️ No metadata extraction request topic found in configuration")
            
            # Setup connections through manager
            await self.connection_manager.setup_producer()
            
            # Setup consumer with topics from registered handlers
            topics = list(self.event_handlers.keys())
            if topics:
                await self.connection_manager.setup_consumer(topics)
            
            if not self.connection_manager.consumer:
                raise ValueError("Failed to setup Kafka consumer")
            
            self.running = True
            
            
            # Start consuming messages
            await self._start_consuming()
            
        except Exception as e:
            logger.error(f"❌ Failed to start Kafka transport service: {e}")
            await self.stop()
            raise
    
    async def _start_consuming(self):
        """Start consuming messages from Kafka using native async iteration."""
        logger.info("📡 Starting to consume Kafka messages with native async iteration")
        
        try:
            # Native async iteration over messages - no blocking!
            async for message in self.connection_manager.consumer:
                if not self.running:
                    logger.info("🛑 Stopping message consumption")
                    break
                    
                try:
                    await self._process_kafka_message(message)
                except Exception as e:
                    logger.error(f"❌ Error processing Kafka message: {e}", exc_info=True)
                    
        except Exception as e:
            if self.running:
                logger.error(f"❌ Kafka consumption error: {e}")
            raise
    
    async def _process_kafka_message(self, message):
        """Process a single Kafka message with robust deserialization."""
        try:
            topic = message.topic
            request_id = message.key or "unknown"
            
            # Explicit message deserialization with comprehensive error handling
            message_data = self._deserialize_message_value(message, topic)
            if message_data is None:
                return  # Deserialization failed, already logged
            
            logger.info(f"📥 Kafka message received from topic {topic}: {request_id}")
            logger.debug(f"   Message data keys: {list(message_data.keys()) if isinstance(message_data, dict) else 'Not a dict'}")
            
            # Get handler for this topic
            handler = self.event_handlers.get(topic)
            if not handler:
                logger.warning(f"⚠️ No handler registered for topic: {topic}")
                return
            
            # Call the handler with validated data
            await handler(message, message_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to process Kafka message: {e}", exc_info=True)
    
    def _deserialize_message_value(self, message, topic: str):
        """
        Deserialize Kafka message value with comprehensive error handling.
        
        Args:
            message: Raw Kafka message
            topic: Topic name for error logging
            
        Returns:
            Dict or None: Deserialized message data or None if deserialization fails
        """
        try:
            # Check if message value is already deserialized by aiokafka
            if isinstance(message.value, dict):
                return message.value
            
            # Handle raw bytes - explicit JSON deserialization
            if isinstance(message.value, bytes):
                try:
                    decoded_string = message.value.decode('utf-8')
                    message_data = json.loads(decoded_string)
                    
                    if not isinstance(message_data, dict):
                        logger.error(f"❌ Message from {topic} is not a JSON object, got {type(message_data)}")
                        logger.debug(f"   Raw value: {message.value[:200]}...")
                        return None
                    
                    return message_data
                    
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.error(f"❌ Failed to deserialize JSON message from {topic}: {e}")
                    logger.debug(f"   Raw message value: {message.value[:200]}...")
                    return None
            
            # Handle string values
            elif isinstance(message.value, str):
                try:
                    message_data = json.loads(message.value)
                    
                    if not isinstance(message_data, dict):
                        logger.error(f"❌ Message from {topic} is not a JSON object, got {type(message_data)}")
                        return None
                    
                    return message_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse JSON string from {topic}: {e}")
                    logger.debug(f"   String value: {message.value[:200]}...")
                    return None
            
            # Unexpected value type
            else:
                logger.error(f"❌ Unexpected message value type from {topic}: {type(message.value)}")
                logger.debug(f"   Value: {message.value}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Unexpected error deserializing message from {topic}: {e}")
            return None
    
    async def _handle_metadata_extraction_request(self, message, message_data: Dict[str, Any]):
        """
        Handle metadata extraction request by delegating to the metadata service.
        
        The transport layer is agnostic about HOW extraction happens.
        All content retrieval and extraction logic is delegated to the MetadataExtractionService.
        
        Flow:
        1. Parse request event
        2. Call metadata extraction service (passing all parameters)
        3. Publish success or failure event
        """
        start_time = time.time()
        extraction_request = None
        
        try:
            # Parse request
            try:
                extraction_request = MetadataExtractionRequestEvent(**message_data)
            except Exception as e:
                logger.error(f"❌ Failed to parse metadata extraction request: {e}")
                # Try to extract minimal info to report failure
                rid = message_data.get("request_id") or (message.key.decode('utf-8') if message.key and isinstance(message.key, bytes) else str(message.key)) if message.key else "unknown"
                url = message_data.get("url") or "unknown"
                
                failure_event = MetadataExtractionFailedEvent(
                    request_id=rid,
                    url=url,
                    error_message=f"Request validation failed: {str(e)}",
                    error_type="ValidationError",
                    failed_stage="request_parsing",
                    processing_time_seconds=time.time() - start_time
                )
                await self.event_publisher.publish_extraction_failed(failure_event)
                return

            logger.info(f"🚀 Processing request {extraction_request.request_id}: {extraction_request.url}")
            
            # Delegate EVERYTHING to the metadata extraction service
            # The service decides how to get content (document_url, html_content, or fetch from URL)
            result = await self.metadata_service.extract_metadata(
                url=extraction_request.url,
                request_id=extraction_request.request_id,
                html_content=extraction_request.html_content,
                document_url=extraction_request.document_url
            )
            
            # Publish result based on success/failure
            if result.success:
                # Create and publish completion event
                completion_event = MetadataExtractionCompletedEvent(
                    request_id=extraction_request.request_id,
                    url=extraction_request.url,
                    extracted_metadata=result.intermediate_metadata.model_dump() if result.intermediate_metadata else {},
                    domain_used=result.domain_used or "auto-detected",
                    mappers_used=result.mappers_used or [],
                    processing_time_seconds=time.time() - start_time,
                    artifacts_created=result.artifacts_created or [],
                    json_output_path=getattr(result, 'json_output_path', None),
                    metadata_statistics={'total_fields': len(result.intermediate_metadata.model_dump()) if result.intermediate_metadata else 0},
                    quality_assessment={'extraction_successful': True} if result.intermediate_metadata else None,
                    extraction_details={},
                    workflow_stages_completed=['received', 'metadata_extraction', 'completed'],
                    total_fields_extracted=len(result.intermediate_metadata.model_dump()) if result.intermediate_metadata else 0
                )
                await self.event_publisher.publish_extraction_completed(completion_event)
                self._requests_processed += 1
                logger.info(f"✅ Request {extraction_request.request_id} completed successfully in {completion_event.processing_time_seconds:.2f}s")
            else:
                # Extraction failed
                await self._publish_failure_event(
                    extraction_request,
                    result.error_message or "Unknown error",
                    result.error_type or "MetadataExtractionError",
                    result.failed_stage or "content_processing",
                    time.time() - start_time,
                    extraction_result=result
                )
                self._requests_processed += 1
                
        except Exception as e:
            logger.error(f"❌ Failed to handle metadata extraction request: {e}", exc_info=True)
            if extraction_request:
                await self._publish_failure_event(
                    extraction_request,
                    str(e),
                    "UnexpectedError",
                    "request_processing",
                    time.time() - start_time
                )
    
    async def _publish_failure_event(
        self,
        extraction_request: MetadataExtractionRequestEvent,
        error_message: str,
        error_type: str,
        failed_stage: str,
        processing_time: float,
        extraction_result: Optional[ExtractionResult] = None
    ) -> None:
        """
        Publish a metadata extraction failure event.
        
        Args:
            extraction_request: Original extraction request
            error_message: Error message describing the failure
            error_type: Type/category of error
            failed_stage: Stage where processing failed
            processing_time: Time spent processing before failure
        """
        try:
            details = {'original_request': extraction_request.model_dump()}
            if extraction_result:
                details['extraction_result'] = extraction_result.to_dict()
                # Remove large fields that are already in the top-level event to save space
                if 'error_message' in details['extraction_result']:
                    del details['extraction_result']['error_message']
                if 'error_type' in details['extraction_result']:
                    del details['extraction_result']['error_type']
                if 'failed_stage' in details['extraction_result']:
                    del details['extraction_result']['failed_stage']

            failure_event = MetadataExtractionFailedEvent(
                request_id=extraction_request.request_id,
                url=extraction_request.url,
                error_message=error_message,
                error_type=error_type,
                failed_stage=failed_stage,
                processing_time_seconds=processing_time,
                details=details
            )
            await self.event_publisher.publish_extraction_failed(failure_event)
            logger.error(
                f"❌ Request {extraction_request.request_id} failed at stage '{failed_stage}': "
                f"{error_message}"
            )
        except Exception as e:
            logger.error(f"Failed to publish failure event: {e}", exc_info=True)
    
    
    
    
    
    

    
    
    
    
    
    async def publish_metadata_extraction_request(self, event: MetadataExtractionRequestEvent) -> bool:
        """Publish a metadata extraction request event to Kafka."""
        return await self.event_publisher._publish_event(
            topic=self.topics['metadata_extraction_requests'],
            key=event.request_id,
            event_data=event.model_dump()
        )
    
    
    async def stop(self):
        """Stop the Kafka transport service and cleanup resources."""
        logger.info("🛑 Stopping Kafka transport service")
        self.running = False
        
        # Use connection manager's cleanup method
        await self.connection_manager.cleanup()
        
        logger.info("✅ Kafka transport service stopped")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of Kafka transport service."""
        try:
            health_status = {
                "service": "kafka_transport",
                "running": self.running,
                "producer_ready": self.connection_manager.producer is not None,
                "consumer_ready": self.connection_manager.consumer is not None,
                "registered_topics": list(self.event_handlers.keys()),
                "requests_processed": self._requests_processed
            }

            return {
                "healthy": self.connection_manager.producer is not None,
                "running": self.running,
                "details": health_status,
            }

        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    
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
            return await self.event_publisher._publish_event(destination, key, message)
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
            'capabilities': {
                'async_processing': True,
                'event_driven': True,
                'scalable': True,
                'persistent_messaging': True,
                'metadata_extraction': True
            },
            'status': {
                'running': self.running,
                'producer_ready': self.connection_manager.producer is not None,
                'consumer_ready': self.connection_manager.consumer is not None,
                'registered_handlers': len(self.event_handlers),
                'requests_processed': self._requests_processed
            },
            'components': {
                'connection_manager': 'KafkaConnectionManager',
                'event_publisher': 'EventPublisher',
                'metadata_service': 'MetadataExtractionService'
            },
            'supported_events': self.event_publisher.get_supported_events()
        }
    
