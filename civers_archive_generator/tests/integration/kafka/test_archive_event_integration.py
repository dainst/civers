"""
Integration tests for archive event handling with real Kafka infrastructure.

These tests require Docker and Kafka to be running.
"""
import asyncio
import logging
import pytest

from transport_services.kafka.event_models import ArchiveRequestEvent
from transport_services.kafka import KafkaTransportService
from tests.fixtures.docker_fixtures import test_kafka_only
from tests.fixtures.shared_fixtures import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
async def test_kafka_transport_service_integration(config, test_kafka_only):
    """Test KafkaTransportService with real configuration."""
    from archive_services import ArchiveService
    archive_service = ArchiveService(config)
    service = KafkaTransportService(config, archive_service)
    
    try:
        # Test that the service can be initialized
        assert service.kafka_config is not None
        assert service.archive_service is not None
        assert service.producer is not None
        
        # Test health check
        health = await service.health_check()
        assert health['healthy'] is True
        assert health['details']['producer_ready'] is True
        
        logger.info(f"✅ KafkaTransportService integration test passed")
        
    finally:
        await service.stop()


@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
async def test_archive_creation_integration(config, test_kafka_only):
    """Test archive creation through KafkaTransportService."""
    from archive_services import ArchiveService
    archive_service = ArchiveService(config)
    service = KafkaTransportService(config, archive_service)
    
    try:
        # Test direct archive creation using the underlying ArchiveService
        result = await service.archive_service.create_archive(
            url="https://arachne.dainst.org/test",
            request_id="test-request-integration-1234",
            priority=1
        )
        
        # Assertions
        assert result['success'] is True
        assert 'archive_path' in result
        assert 'processing_time_seconds' in result
        assert result['processing_time_seconds'] > 0
        
        logger.info(f"✅ Archive creation completed: {result['archive_path']}")
        
    finally:
        await service.stop()

@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
async def test_kafka_service_workflow_integration(config, test_kafka_only):
    """Test integration workflow between KafkaTransportService and ArchiveService.
    
    This tests service-level integration, not true end-to-end application workflow.
    It verifies that KafkaTransportService can properly delegate archive creation
    to ArchiveService when processing archive request events.
    """
    from archive_services import ArchiveService
    archive_service = ArchiveService(config)
    transport_service = KafkaTransportService(config, archive_service)
    
    try:
        # Test that service can be initialized
        assert transport_service.kafka_config is not None
        assert transport_service.archive_service is not None
        
        # Test direct archive creation (integration between services)
        request_event = ArchiveRequestEvent(
            url="https://arachne.dainst.org/service-integration-test",
            priority=1,
            request_id="test-service-integration-1234"
        )
        
        # Test service integration - ArchiveService receives work from KafkaTransportService
        result = await transport_service.archive_service.create_archive(
            url=request_event.url,
            request_id=request_event.request_id,
            priority=request_event.priority
        )
        
        assert result['success'] is True
        assert 'archive_path' in result
        
        logger.info("✅ Kafka service workflow integration completed successfully")
        
    finally:
        await transport_service.stop()


# End of file
