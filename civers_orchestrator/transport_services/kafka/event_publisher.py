"""
Event Publisher for Kafka.

Simple, focused component that handles event publishing to Kafka topics.
Used ONLY by KafkaTransportService - orchestrator has no knowledge of this.
"""

import json
from typing import Any, Dict

from pydantic import BaseModel

from configs.logging_config import get_logger

logger = get_logger(__name__)


class EventPublisher:
    """
    Handles event publishing to Kafka topics.

    This class provides a simple interface for publishing Pydantic event models
    to Kafka topics. It's used exclusively by KafkaTransportService.

    Responsibilities:
    - Serialize Pydantic models to JSON
    - Publish to Kafka via producer
    - Handle publishing errors

    What it DOES NOT do:
    - NO business logic
    - NO workflow knowledge
    - NO orchestration
    """

    def __init__(self, kafka_producer, topics: Dict[str, str]):
        """
        Initialize the event publisher.

        Args:
            kafka_producer: Kafka producer instance (from kafka-python)
            topics: Dictionary mapping topic names to topic strings
        """
        self.producer = kafka_producer
        self.topics = topics

    def publish_event(
        self,
        topic: str,
        key: str,
        event: BaseModel
    ) -> bool:
        """
        Publish any Pydantic event model to Kafka.

        Args:
            topic: Kafka topic name
            key: Message key (usually request_id)
            event: Pydantic event model instance

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            if not self.producer:
                logger.error("❌ Kafka producer not initialized")
                return False

            # Serialize event to dict
            event_data = event.model_dump()

            # Publish to Kafka
            future = self.producer.send(
                topic=topic,
                key=key,
                value=event_data
            )

            # Wait for acknowledgment
            future.get(timeout=10)

            logger.debug(f"📤 Published {event.__class__.__name__} to {topic}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False

    def publish_dict(
        self,
        topic: str,
        key: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Publish a dictionary directly to Kafka.

        Useful for cases where event model isn't available.

        Args:
            topic: Kafka topic name
            key: Message key
            data: Dictionary to publish

        Returns:
            bool: True if published successfully
        """
        try:
            if not self.producer:
                logger.error("❌ Kafka producer not initialized")
                return False

            # Publish to Kafka
            future = self.producer.send(
                topic=topic,
                key=key,
                value=data
            )

            # Wait for acknowledgment
            future.get(timeout=10)

            logger.debug(f"📤 Published dict to {topic}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish dict to {topic}: {e}")
            return False
