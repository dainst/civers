import pytest
import asyncio
import json
import uuid
import time
from unittest.mock import AsyncMock
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from transport_services.kafka.kafka_transport_service import KafkaTransportService
from configs.models import ConfigDataModel

@pytest.mark.integration
@pytest.mark.usefixtures("kafka_available")
class TestKafkaTransportFlowIntegration:
    """Integration tests verifying Kafka event handling and processing loop."""

    @pytest.mark.asyncio
    async def test_kafka_flow_success(self, integration_kafka_config: ConfigDataModel):
        """Test sending an archive request via Kafka and getting completed event."""
        # 1. Mock ArchiveService
        mock_archive_service = AsyncMock()
        mock_archive_service.create_archive.return_value = {
            'success': True,
            'archive_path': '/tmp/test_archives/success.wacz',
            'artifacts_created': ['warc', 'screenshot'],
            'processing_time_seconds': 1.5
        }

        # 2. Get bootstrap servers and topic configurations
        kafka_config = integration_kafka_config.app.get_kafka_config()
        bootstrap_servers = kafka_config.bootstrap_servers
        topics = kafka_config.topics

        # 3. Create Kafka transport service
        transport_service = KafkaTransportService(integration_kafka_config, mock_archive_service)
        
        # Start transport in a background task
        transport_task = asyncio.create_task(transport_service.start())
        
        # Allow time for transport service to start and connect
        await asyncio.sleep(2)

        # 4. Produce request event
        request_id = f"test-flow-{uuid.uuid4().hex[:8]}"
        request_payload = {
            "request_id": request_id,
            "url": "https://example.com",
            "priority": 1,
            "created_at": "2026-06-28T12:00:00Z"
        }

        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        await producer.start()
        try:
            await producer.send_and_wait(
                topic=topics["archive_requests"],
                key=request_id,
                value=request_payload
            )
        finally:
            await producer.stop()

        # 5. Consume and verify status and completed events
        consumer = AIOKafkaConsumer(
            topics["archive_status"],
            topics["archive_completed"],
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='earliest',
            consumer_timeout_ms=5000
        )
        await consumer.start()

        status_updates = []
        completed_events = []

        try:
            # Poll messages for a maximum of 5 seconds
            start_time = time.time()
            while time.time() - start_time < 5.0:
                msg_pack = await consumer.getmany(timeout_ms=1000)
                for tp, messages in msg_pack.items():
                    for msg in messages:
                        if msg.topic == topics["archive_status"] and msg.value.get("request_id") == request_id:
                            status_updates.append(msg.value)
                        elif msg.topic == topics["archive_completed"] and msg.value.get("request_id") == request_id:
                            completed_events.append(msg.value)
                if len(completed_events) >= 1:
                    break
        finally:
            await consumer.stop()

        # 6. Stop transport service
        await transport_service.stop()
        try:
            await transport_task
        except asyncio.CancelledError:
            pass

        # 7. Assertions
        mock_archive_service.create_archive.assert_called_once_with(
            "https://example.com", request_id, 1
        )
        
        # Verify we received processing and completed status updates
        statuses = [u["status"] for u in status_updates]
        assert "processing" in statuses
        assert "completed" in statuses
        
        # Verify completed event was sent
        assert len(completed_events) == 1
        assert completed_events[0]["archive_path"] == '/tmp/test_archives/success.wacz'
