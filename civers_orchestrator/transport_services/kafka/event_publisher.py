"""
Async Event Publisher for Kafka in CiVers Orchestrator.

Handles asynchronous event publishing using aiokafka.
"""

import logging
from typing import Any, Dict
from pydantic import BaseModel

from configs.logging_config import get_logger

logger = get_logger(__name__)


class EventPublisher:
    """
    Handles async event publishing to Kafka topics.
    """

    def __init__(self, connection_manager, topics: Dict[str, str]):
        """
        Initialize the event publisher.

        Args:
            connection_manager: Kafka connection manager for producer access
            topics: Mapping of topic keys to topic strings
        """
        self.connection_manager = connection_manager
        self.topics = topics

    async def publish_event(
        self,
        topic: str,
        key: str,
        event: BaseModel
    ) -> bool:
        """
        Publish any Pydantic event model to Kafka asynchronously.

        Args:
            topic: Kafka topic name or key
            key: Message key (request_id)
            event: Pydantic event model instance

        Returns:
            bool: True if published successfully
        """
        try:
            if not self.connection_manager.producer:
                logger.error("❌ Kafka producer not initialized")
                return False

            # Serialize and send
            await self.connection_manager.producer.send(
                topic=topic,
                key=key,
                value=event.model_dump()
            )

            logger.debug(f"📤 Published {event.__class__.__name__} to {topic}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False

    async def publish_dict(
        self,
        topic: str,
        key: str,
        data: Dict[str, Any]
    ) -> bool:
        """Publish a dictionary directly to Kafka asynchronously."""
        try:
            if not self.connection_manager.producer:
                logger.error("❌ Kafka producer not initialized")
                return False

            await self.connection_manager.producer.send(
                topic=topic,
                key=key,
                value=data
            )

            logger.debug(f"📤 Published dict to {topic}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish dict to {topic}: {e}")
            return False
