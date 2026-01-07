"""
Kafka Producer Service for Civers Archive Web Interface.

This service handles publishing events to Kafka topics for the archive request feature.
It follows the patterns established in the civers_orchestrator's KafkaTransportService.

Key Features:
- Lazy initialization of Kafka producer
- Graceful handling of Kafka connection failures
- Health check capability
- Support for publishing Pydantic event models
"""

import json
import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel

from configs.models import KafkaConfig

logger = logging.getLogger(__name__)


class KafkaProducerError(Exception):
    """Exception raised for Kafka producer errors."""
    pass


class KafkaProducerService:
    """
    Kafka producer service for publishing archive request events.

    This service provides a simple interface for publishing events to Kafka topics.
    It handles producer initialization, connection management, and error handling.

    Usage:
        # Initialize with config
        producer_service = KafkaProducerService(kafka_config)
        
        # Initialize the producer (can be done lazily or at startup)
        await producer_service.initialize()
        
        # Publish an event
        success = producer_service.publish_event(
            topic="orchestrator.requests",
            key="request-123",
            event=my_event
        )
        
        # Shutdown gracefully
        await producer_service.shutdown()

    Attributes:
        config: KafkaConfig instance with connection settings
        producer: KafkaProducer instance (initialized lazily)
        is_initialized: Whether the producer has been successfully initialized
    """

    def __init__(self, config: Optional[KafkaConfig] = None, enabled: bool = True):
        """
        Initialize the Kafka producer service.

        Args:
            config: KafkaConfig instance.
            enabled: Whether Kafka integration is enabled.
        """
        self.config = config
        self._enabled = enabled
        self.producer = None
        self.is_initialized = False
        self._initialization_error: Optional[str] = None

    @property
    def is_enabled(self) -> bool:
        """Check if Kafka is enabled in configuration."""
        return self.config is not None and self._enabled

    async def initialize(self) -> bool:
        """
        Initialize the Kafka producer.

        Returns:
            bool: True if initialization successful, False otherwise

        Note:
            This method is idempotent - calling it multiple times is safe.
            If already initialized, it returns True immediately.
        """
        if self.is_initialized:
            return True

        if not self.is_enabled:
            logger.info("Kafka is disabled - producer not initialized")
            return False

        try:
            # Import kafka-python here to allow application to run without Kafka
            from kafka import KafkaProducer

            logger.info(f"Connecting to Kafka at {self.config.bootstrap_servers}...")

            self.producer = KafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks=self.config.producer.acks if self.config.producer.acks != "all" else "all",
                retries=self.config.producer.retries,
                max_in_flight_requests_per_connection=1,
                request_timeout_ms=self.config.producer.request_timeout_ms,
                api_version_auto_timeout_ms=self.config.producer.api_version_timeout_ms,
            )

            self.is_initialized = True
            self._initialization_error = None
            logger.info("Kafka producer initialized successfully")
            return True

        except ImportError as e:
            self._initialization_error = f"kafka-python not installed: {e}"
            logger.error(self._initialization_error)
            return False

        except Exception as e:
            self._initialization_error = f"Failed to connect to Kafka: {e}"
            logger.error(self._initialization_error)
            return False

    async def publish_event(
        self,
        topic_key: str,
        event: Optional[BaseModel] = None,
        event_data: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Publish a Pydantic event model to a Kafka topic.

        Args:
            topic: Kafka topic name
            key: Message key (usually request_id for partitioning)
            event: Pydantic event model instance
            timeout: Timeout in seconds for send confirmation

        Returns:
            bool: True if published successfully, False otherwise

        Raises:
            KafkaProducerError: If producer is not initialized

        Example:
            >>> event = OrchestratorRequestEvent(request_id="123", url="https://...")
            >>> success = producer_service.publish_event(
            ...     topic="orchestrator.requests",
            ...     key="123",
            ...     event=event
            ... )
        """
        if not self.is_initialized or not self.producer:
            error_msg = self._initialization_error or "Producer not initialized"
            logger.error(f"Cannot publish: {error_msg}")
            raise KafkaProducerError(error_msg)

        if timeout is None:
            timeout = self.config.producer.publish_timeout_seconds if self.config else 10.0

        try:
            # 1. Resolve topic
            topic = self.get_topic(topic_key)
            
            # 2. Resolve data and key
            if event:
                data = event.model_dump()
                # Use request_id as default key if present for better partitioning
                final_key = key or getattr(event, 'request_id', None)
            elif event_data:
                data = event_data
                final_key = key or data.get('request_id')
            else:
                raise ValueError("Either 'event' or 'event_data' must be provided")

            # 3. Publish to Kafka (offload blocking bit to thread if necessary, 
            # but kafka-python send is non-blocking, only future.get blocks)
            import asyncio
            
            def _send():
                future = self.producer.send(
                    topic=topic,
                    key=final_key,
                    value=data
                )
                return future.get(timeout=timeout)

            # Execute the blocking future.get() in a thread to keep event loop free
            record_metadata = await asyncio.to_thread(_send)

            logger.info(
                f"Published event to {topic} (key={final_key}, offset={record_metadata.offset})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish event with key '{topic_key}': {e}")
            return False

    def publish_dict(
        self,
        topic: str,
        key: str,
        data: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> bool:
        """
        Publish a dictionary directly to Kafka.

        Useful for cases where event model isn't available or for simple messages.

        Args:
            topic: Kafka topic name
            key: Message key
            data: Dictionary to publish
            timeout: Timeout in seconds for send confirmation

        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.is_initialized or not self.producer:
            error_msg = self._initialization_error or "Producer not initialized"
            logger.error(f"Cannot publish: {error_msg}")
            raise KafkaProducerError(error_msg)

        if timeout is None:
            timeout = self.config.producer.publish_timeout_seconds if self.config else 10.0

        try:
            # Publish to Kafka
            future = self.producer.send(
                topic=topic,
                key=key,
                value=data
            )

            # Wait for acknowledgment
            future.get(timeout=timeout)

            logger.debug(f"Published dict to {topic} (key={key})")
            return True

        except Exception as e:
            logger.error(f"Failed to publish dict to {topic}: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the Kafka producer.

        Returns:
            Dict with health status and details

        Example:
            >>> health = await producer_service.health_check()
            >>> print(health)
            {
                "healthy": True,
                "enabled": True,
                "initialized": True,
                "bootstrap_servers": "localhost:29092"
            }
        """
        if not self.is_enabled:
            return {
                "healthy": True,  # Healthy because intentionally disabled
                "enabled": False,
                "initialized": False,
                "message": "Kafka is disabled in configuration"
            }

        if not self.is_initialized:
            return {
                "healthy": False,
                "enabled": True,
                "initialized": False,
                "error": self._initialization_error or "Producer not initialized"
            }

        # Try a simple metadata request to check connection
        try:
            # Check if producer can reach broker
            if self.producer:
                # Get cluster metadata (lightweight check)
                metadata = self.producer.bootstrap_connected()
                return {
                    "healthy": metadata,
                    "enabled": True,
                    "initialized": True,
                    "bootstrap_servers": self.config.bootstrap_servers,
                    "connected": metadata
                }
        except Exception as e:
            return {
                "healthy": False,
                "enabled": True,
                "initialized": True,
                "error": str(e)
            }

        return {
            "healthy": False,
            "enabled": True,
            "initialized": True,
            "error": "Unknown state"
        }

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the Kafka producer.

        Flushes pending messages and closes the connection.
        """
        if self.producer:
            try:
                logger.info("Shutting down Kafka producer...")
                self.producer.flush(timeout=self.config.producer.publish_timeout_seconds)
                self.producer.close(timeout=self.config.producer.shutdown_timeout_seconds)
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.warning(f"Error during producer shutdown: {e}")
            finally:
                self.producer = None
                self.is_initialized = False

    def get_topic(self, topic_name: str) -> str:
        """
        Get the configured topic string for a topic name.
        
        Consistent with KafkaConfig.get_topic() method.

        Args:
            topic_name: Logical topic name (e.g., "orchestrator_requests")

        Returns:
            Configured topic string

        Raises:
            ValueError: If topic not found in configuration
        """
        if not self.config or not self.config.topics:
            raise ValueError("Kafka topics not configured")

        # Topics is now a Dict[str, str] for consistency with other components
        topic_value = self.config.topics.get(topic_name)
        if not topic_value:
            raise ValueError(f"Topic '{topic_name}' not found in configuration. Available: {list(self.config.topics.keys())}")

        return topic_value
