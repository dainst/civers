# tests/integration/test_kafka_integration_new.py
"""Integration tests for transport-agnostic orchestrator with Kafka.

These tests validate the refactored architecture (Tasks 11-14):
- Orchestrator returns transport-agnostic instructions
- Adapter translates component → Kafka specifics
- Transport service executes via adapter

Requires: docker compose up -d
"""
import asyncio

import pytest

from transport_services.kafka.event_models import OrchestratorRequestEvent


@pytest.mark.integration
class TestKafkaIntegrationBasic:
    """Basic integration tests with real Kafka."""

    @pytest.mark.asyncio
    async def test_service_starts_and_stops(self, kafka_transport_service):
        """Test that service can start and stop successfully with adapter."""
        # Start service in background
        start_task = asyncio.create_task(kafka_transport_service.start())

        # Wait for service to start
        await asyncio.sleep(2)

        # Verify service is running
        assert kafka_transport_service.running is True
        assert kafka_transport_service.connection_manager.consumer is not None
        assert kafka_transport_service.adapter is not None

        # Stop service
        await kafka_transport_service.stop()
        start_task.cancel()

        # Verify service stopped
        assert kafka_transport_service.running is False

    @pytest.mark.asyncio
    async def test_health_check_with_real_kafka(self, kafka_transport_service):
        """Test health check with real Kafka connection."""
        start_task = asyncio.create_task(kafka_transport_service.start())
        await asyncio.sleep(2)

        try:
            health = await kafka_transport_service.health_check()
            assert health["healthy"] is True
            assert health["details"]["producer_ready"] is True
            assert health["details"]["consumer_ready"] is True
        finally:
            await kafka_transport_service.stop()
            start_task.cancel()

    @pytest.mark.asyncio
    async def test_adapter_integration(self, kafka_transport_service):
        """Test that adapter is properly integrated."""
        # Verify adapter exists
        assert kafka_transport_service.adapter is not None

        # Verify adapter has component mappings
        assert "archive_generator" in kafka_transport_service.adapter.component_mappings
        assert "metadata_extractor" in kafka_transport_service.adapter.component_mappings

        # Test adapter can get request destination
        archive_topic = kafka_transport_service.adapter.get_request_destination("archive_generator")
        assert archive_topic == "test.archive.requests"

        # Test adapter can get response destinations
        archive_responses = kafka_transport_service.adapter.get_response_destinations("archive_generator")
        assert archive_responses["success"] == "test.archive.completed"
        assert archive_responses["failure"] == "test.archive.failed"


@pytest.mark.integration
class TestTransportAgnosticInstructions:
    """Test that orchestrator instructions are transport-agnostic."""

    @pytest.mark.asyncio
    async def test_orchestrator_returns_transport_agnostic_instruction(
        self, kafka_transport_service, mock_orchestrator_service
    ):
        """Test that orchestrator returns instruction without Kafka knowledge."""
        # Simulate orchestrator request
        request_event = OrchestratorRequestEvent(
            request_id="test-001",
            url="https://example.com",
            workflow_name="test_workflow",
        )

        # Call orchestrator's start_workflow
        instruction = mock_orchestrator_service.start_workflow(
            request_id=request_event.request_id,
            url=request_event.url,
            workflow_name=request_event.workflow_name,
        )

        # Verify instruction is transport-agnostic (no Kafka fields)
        assert hasattr(instruction, "component")
        assert hasattr(instruction, "input_schema")
        assert not hasattr(instruction, "input_topic")  # ❌ Should NOT have Kafka topic
        assert not hasattr(instruction, "input_event_model")  # ❌ Should NOT have Kafka event model

        assert instruction.component == "archive_generator"
        assert instruction.input_schema == "ArchiveRequest"

    @pytest.mark.asyncio
    async def test_adapter_translates_instruction_to_kafka(
        self, kafka_transport_service, mock_orchestrator_service
    ):
        """Test that adapter translates transport-agnostic instruction to Kafka operation."""
        # Get transport-agnostic instruction from orchestrator
        instruction = mock_orchestrator_service.start_workflow(
            request_id="test-002",
            url="https://example.com",
        )

        # Adapter should translate it to Kafka operation
        kafka_operation = kafka_transport_service.adapter.translate_instruction(instruction)

        # Verify translation contains Kafka-specific details
        assert "topic" in kafka_operation
        assert "event_model" in kafka_operation
        assert kafka_operation["topic"] == "test.archive.requests"
        assert kafka_operation["event_model"] == "ArchiveRequestEvent"


