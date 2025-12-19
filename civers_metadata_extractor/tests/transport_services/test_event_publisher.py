"""
Unit tests for EventPublisher

This module tests the EventPublisher class functionality including
event publishing, topic routing, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from transport_services.kafka.event_publisher import EventPublisher
from transport_services.kafka.event_models import (
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent,
    WorkflowProgressEvent
)


class TestEventPublisher:
    """Test cases for EventPublisher class."""
    
    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager."""
        manager = Mock()
        manager.producer = AsyncMock()
        
        # Mock successful send operation - return awaitable
        manager.producer.send.return_value = AsyncMock()
        
        return manager
    
    @pytest.fixture
    def sample_topics(self):
        """Create sample topic configuration."""
        return {
            'metadata_extraction_completed': 'metadata.extraction.completed',
            'metadata_extraction_failed': 'metadata.extraction.failed',
            'workflow_progress': 'metadata.workflow.progress'
        }
    
    @pytest.fixture
    def event_publisher(self, mock_connection_manager, sample_topics):
        """Create EventPublisher instance for testing."""
        return EventPublisher(
            connection_manager=mock_connection_manager,
            topics=sample_topics
        )
    
    @pytest.fixture
    def sample_completion_event(self):
        """Create sample completion event."""
        return MetadataExtractionCompletedEvent(
            request_id="test-123",
            url="https://example.com/test",
            extracted_metadata={"title": "Test Title"},
            domain_used="example.com",
            mappers_used=["JsonLDMapper"],
            processing_time_seconds=1.5,
            artifacts_created=["output.json"],
            json_output_path="/path/to/output.json",
            total_fields_extracted=1
        )
    
    @pytest.fixture
    def sample_failure_event(self):
        """Create sample failure event."""
        return MetadataExtractionFailedEvent(
            request_id="test-456",
            url="https://example.com/fail",
            error_message="Test error",
            error_type="ValidationError",
            failed_stage="metadata_extraction",
            processing_time_seconds=0.5,
            details={"error_code": "VALIDATION_FAILED"}
        )
    
    @pytest.fixture
    def sample_progress_event(self):
        """Create sample progress event."""
        return WorkflowProgressEvent(
            request_id="test-789",
            url="https://example.com/progress",
            stage="metadata_extraction",
            stage_status="started",
            progress_percentage=50,
            current_operation="Extracting metadata",
            timestamp="2024-01-29T10:00:00Z"
        )
    
    def test_event_publisher_initialization(self, event_publisher, mock_connection_manager, sample_topics):
        """Test that EventPublisher initializes correctly."""
        assert event_publisher.connection_manager == mock_connection_manager
        assert event_publisher.topics == sample_topics
    
    @pytest.mark.asyncio
    async def test_publish_extraction_completed_success(self, event_publisher, mock_connection_manager, sample_completion_event):
        """Test successful completion event publishing."""
        # Execute
        result = await event_publisher.publish_extraction_completed(sample_completion_event)
        
        # Verify success
        assert result is True
        
        # Verify producer was called correctly
        mock_connection_manager.producer.send.assert_called_once_with(
            topic='metadata.extraction.completed',
            key='test-123',
            value=sample_completion_event.model_dump()
        )
    
    @pytest.mark.asyncio
    async def test_publish_extraction_failed_success(self, event_publisher, mock_connection_manager, sample_failure_event):
        """Test successful failure event publishing."""
        # Execute
        result = await event_publisher.publish_extraction_failed(sample_failure_event)
        
        # Verify success
        assert result is True
        
        # Verify producer was called correctly
        mock_connection_manager.producer.send.assert_called_once_with(
            topic='metadata.extraction.failed',
            key='test-456',
            value=sample_failure_event.model_dump()
        )
    
    @pytest.mark.asyncio
    async def test_publish_workflow_progress_success(self, event_publisher, mock_connection_manager, sample_progress_event):
        """Test successful progress event publishing."""
        # Execute
        result = await event_publisher.publish_workflow_progress(sample_progress_event)
        
        # Verify success
        assert result is True
        
        # Verify producer was called correctly
        mock_connection_manager.producer.send.assert_called_once_with(
            topic='metadata.workflow.progress',
            key='test-789',
            value=sample_progress_event.model_dump()
        )
    
    @pytest.mark.asyncio
    async def test_publish_event_with_no_producer(self, sample_topics, sample_completion_event):
        """Test publishing when producer is not initialized."""
        # Setup connection manager without producer
        mock_connection_manager = Mock()
        mock_connection_manager.producer = None
        
        event_publisher = EventPublisher(mock_connection_manager, sample_topics)
        
        # Execute
        result = await event_publisher.publish_extraction_completed(sample_completion_event)
        
        # Verify failure
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_event_with_kafka_error(self, event_publisher, mock_connection_manager, sample_completion_event):
        """Test publishing when Kafka operation fails."""
        # Setup producer to raise exception
        mock_connection_manager.producer.send.side_effect = Exception("Kafka connection failed")
        
        # Execute
        result = await event_publisher.publish_extraction_completed(sample_completion_event)
        
        # Verify failure
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_event_with_timeout(self, event_publisher, mock_connection_manager, sample_completion_event):
        """Test publishing when acknowledgment times out."""
        # Setup producer to raise exception on send
        mock_connection_manager.producer.send.side_effect = Exception("Timeout")
        
        # Execute
        result = await event_publisher.publish_extraction_completed(sample_completion_event)
        
        # Verify failure
        assert result is False
    
    def test_get_supported_events(self, event_publisher):
        """Test getting list of supported event types."""
        supported_events = event_publisher.get_supported_events()
        
        expected_events = [
            'MetadataExtractionCompletedEvent',
            'MetadataExtractionFailedEvent',
            'WorkflowProgressEvent'
        ]
        
        assert supported_events == expected_events
    
    def test_get_topic_mapping(self, event_publisher, sample_topics):
        """Test getting topic mapping configuration."""
        topic_mapping = event_publisher.get_topic_mapping()
        
        expected_mapping = {
            'metadata_extraction_completed': 'metadata.extraction.completed',
            'metadata_extraction_failed': 'metadata.extraction.failed',
            'workflow_progress': 'metadata.workflow.progress'
        }
        
        assert topic_mapping == expected_mapping
    
    @pytest.mark.asyncio
    async def test_topic_fallback_for_completion_event(self, mock_connection_manager):
        """Test topic fallback for completion events."""
        # Setup topics with legacy name
        topics = {
            'metadata_extracted': 'legacy.metadata.extracted',  # Legacy topic name
            'metadata_extraction_failed': 'metadata.extraction.failed'
        }
        
        event_publisher = EventPublisher(mock_connection_manager, topics)
        
        # Create completion event
        completion_event = MetadataExtractionCompletedEvent(
            request_id="test-fallback",
            url="https://example.com",
            extracted_metadata={},
            domain_used="example.com",
            mappers_used=[],
            processing_time_seconds=1.0,
            artifacts_created=[],
            total_fields_extracted=0
        )
        
        # Execute async
        result = await event_publisher._publish_event(
            topic=topics.get('metadata_extraction_completed', topics.get('metadata_extracted')),
            key=completion_event.request_id,
            event_data=completion_event.model_dump()
        )
        
        # Verify fallback topic was used
        assert result is True
        mock_connection_manager.producer.send.assert_called_with(
            topic='legacy.metadata.extracted',  # Should use fallback
            key='test-fallback',
            value=completion_event.model_dump()
        )
    
    @pytest.mark.asyncio
    async def test_publish_event_core_functionality(self, event_publisher, mock_connection_manager):
        """Test core _publish_event method directly."""
        test_data = {"test": "data", "key": "value"}
        
        # Execute
        result = await event_publisher._publish_event(
            topic="test.topic",
            key="test-key",
            event_data=test_data
        )
        
        # Verify success
        assert result is True
        
        # Verify producer interaction
        mock_connection_manager.producer.send.assert_called_once_with(
            topic="test.topic",
            key="test-key", 
            value=test_data
        )