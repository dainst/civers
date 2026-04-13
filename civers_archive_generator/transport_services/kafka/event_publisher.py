"""
Event Publisher for CiVers Archive Generator.

This module provides the EventPublisher class that handles publishing events
to Kafka topics using the asynchronous connection manager.
"""

import logging
from typing import Dict, Any

from .event_models import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
    ArchiveStatusEvent
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Handles event publishing for the Archive Generator.
    """
    
    def __init__(self, connection_manager, topics: Dict[str, str]):
        """
        Initialize the event publisher.
        
        Args:
            connection_manager: Kafka connection manager for producer access
            topics: Dictionary mapping event types to topic names
        """
        self.connection_manager = connection_manager
        self.topics = topics
    
    async def publish_archive_completed(self, event: ArchiveCompletedEvent) -> bool:
        """Publish archive completion event."""
        try:
            topic = self.topics.get('archive_completed')
            if not topic:
                logger.error("❌ No archive_completed topic found")
                return False
                
            return await self._publish_event(
                topic=topic,
                key=event.request_id,
                event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish archive completed event: {e}")
            return False
    
    async def publish_archive_failed(self, event: ArchiveFailedEvent) -> bool:
        """Publish archive failure event."""
        try:
            topic = self.topics.get('archive_failed')
            if not topic:
                logger.error("❌ No archive_failed topic found")
                return False
                
            return await self._publish_event(
                topic=topic,
                key=event.request_id,
                event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish archive failed event: {e}")
            return False
    
    async def publish_status_update(self, event: ArchiveStatusEvent) -> bool:
        """Publish status update event."""
        try:
            topic = self.topics.get('archive_status')
            if not topic:
                logger.error("❌ No archive_status topic found")
                return False
                
            return await self._publish_event(
                topic=topic,
                key=event.request_id,
                event_data=event.model_dump()
            )
        except Exception as e:
            logger.error(f"❌ Failed to publish status update event: {e}")
            return False
    
    async def _publish_event(self, topic: str, key: str, event_data: Dict[str, Any]) -> bool:
        """Core async event publishing method."""
        try:
            if not self.connection_manager.producer:
                logger.error("❌ Kafka producer not initialized")
                return False
            
            await self.connection_manager.producer.send(
                topic=topic,
                key=key,
                value=event_data
            )
            
            logger.debug(f"📤 Event published to {topic}, key: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False
