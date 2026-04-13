"""
Event Publisher

This module provides the EventPublisher class that handles publishing events
to Kafka topics with essential functionality for MVP requirements.
"""

import logging
from typing import Any

from .event_models import (
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent,
    WorkflowProgressEvent,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Handles event publishing to Kafka topics.

    This class provides essential event publishing functionality for the
    metadata extraction workflow, focusing on MVP requirements only.

    Responsibilities:
    - Event serialization and publishing
    - Topic routing for different event types
    - Publishing error handling
    - Core event validation
    """

    def __init__(self, connection_manager, topics: dict[str, str]):
        """
        Initialize the event publisher.

        Args:
            connection_manager: Kafka connection manager for producer access
            topics: Dictionary mapping event types to topic names
        """
        self.connection_manager = connection_manager
        self.topics = topics

    async def publish_extraction_completed(self, event: MetadataExtractionCompletedEvent) -> bool:
        """
        Publish metadata extraction completion event.

        Args:
            event: Completion event to publish

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            # Check both internal and shared config topic keys
            topic = (
                self.topics.get("metadata_extraction_completed")
                or self.topics.get("metadata_completed")
                or self.topics.get("metadata_extracted")
            )

            if not topic:
                logger.error("❌ No completion topic found in configuration")
                return False

            return await self.publish_event(
                topic=topic, key=event.request_id, event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish extraction completed event: {e}")
            return False

    async def publish_extraction_failed(self, event: MetadataExtractionFailedEvent) -> bool:
        """
        Publish metadata extraction failure event.

        Args:
            event: Failure event to publish

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            # Check both internal and shared config topic keys
            topic = self.topics.get("metadata_extraction_failed") or self.topics.get(
                "metadata_failed"
            )

            if not topic:
                logger.error("❌ No failure topic found in configuration")
                return False

            return await self.publish_event(
                topic=topic, key=event.request_id, event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish extraction failed event: {e}")
            return False

    async def publish_workflow_progress(self, event: WorkflowProgressEvent) -> bool:
        """
        Publish workflow progress event.

        Args:
            event: Progress event to publish

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            topic = self.topics.get("workflow_progress", "metadata.progress")
            return await self.publish_event(
                topic=topic, key=event.request_id, event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish workflow progress event: {e}")
            return False

    async def publish_event(self, topic: str, key: str, event_data: dict[str, Any]) -> bool:
        """
        Publish an event to a Kafka topic.

        Args:
            topic: Kafka topic to publish to
            key: Message key for partitioning
            event_data: Event data as dictionary

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            if not self.connection_manager.producer:
                logger.error("❌ Kafka producer not initialized")
                return False

            await self.connection_manager.producer.send(
                topic=topic,
                key=key,
                value=event_data,
            )

            logger.debug(f"📤 Event published to {topic}, key: {key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False

    def get_supported_events(self) -> list:
        """
        Get list of supported event types.

        Returns:
            List of supported event type names
        """
        return [
            "MetadataExtractionCompletedEvent",
            "MetadataExtractionFailedEvent",
            "WorkflowProgressEvent",
        ]

    def get_topic_mapping(self) -> dict[str, str]:
        """
        Get current topic mapping configuration.

        Returns:
            Dictionary of event types to topic names
        """
        return {
            "metadata_extraction_completed": self.topics.get("metadata_extraction_completed", ""),
            "metadata_extraction_failed": self.topics.get("metadata_extraction_failed", ""),
            "workflow_progress": self.topics.get("workflow_progress", "metadata.progress"),
        }
