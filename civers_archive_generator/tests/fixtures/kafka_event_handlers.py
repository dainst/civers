# kafka_layer/test_event_handlers.py
import logging
import asyncio
from transport_services.kafka.event_models import ArchiveRequestEvent, ArchiveStatusEvent

logger = logging.getLogger(__name__)

class TestEventHandlers:
    """Simple event handlers for testing the consumer."""
    
    @staticmethod
    async def handle_archive_request(event: ArchiveRequestEvent, key: str, partition: int, offset: int):
        """Handle archive request events."""
        logger.info(f"📥 Received archive request:")
        logger.info(f"   Request ID: {event.request_id}")
        logger.info(f"   URL: {event.url}")
        logger.info(f"   Priority: {event.priority}")
        logger.info(f"   Key: {key}, Partition: {partition}, Offset: {offset}")
        
        # Simulate some processing time
        await asyncio.sleep(0.5)
        logger.info(f"✅ Processed archive request: {event.request_id}")
    
    @staticmethod
    async def handle_status_update(event: ArchiveStatusEvent, key: str, partition: int, offset: int):
        """Handle status update events."""
        logger.info(f"📊 Status update:")
        logger.info(f"   Request ID: {event.request_id}")
        logger.info(f"   Status: {event.status}")
        logger.info(f"   Message: {event.message}")
        logger.info(f"   Key: {key}, Partition: {partition}, Offset: {offset}")
    
    @staticmethod
    def handle_archive_completed(event: dict, key: str, partition: int, offset: int):
        """Handle archive completion events (sync handler example)."""
        logger.info(f"🎉 Archive completed:")
        logger.info(f"   Request ID: {event.get('request_id')}")
        logger.info(f"   URL: {event.get('url')}")
        logger.info(f"   Archive path: {event.get('archive_path')}")
        logger.info(f"   Key: {key}, Partition: {partition}, Offset: {offset}")
    
    @staticmethod
    async def handle_archive_failed(event: dict, key: str, partition: int, offset: int):
        """Handle archive failure events."""
        logger.info(f"❌ Archive failed:")
        logger.info(f"   Request ID: {event.get('request_id')}")
        logger.info(f"   URL: {event.get('url')}")
        logger.info(f"   Error: {event.get('error_message')}")
        logger.info(f"   Key: {key}, Partition: {partition}, Offset: {offset}")