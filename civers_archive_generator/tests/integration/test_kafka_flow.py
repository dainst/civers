"""Check real Kafka result events, dead-letter messages and committed offsets."""

import asyncio
import json
import uuid

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from civers_common import CommandBus, Result
from domain.commands import ArchiveCommand
from transport_services.kafka_transport import ArchiveKafkaTransport


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.usefixtures("kafka_available")
@pytest.mark.parametrize("outcome", ["complete", "failed", "invalid", "unroutable"])
async def test_kafka_request_outcome_and_commit(integration_kafka_config, outcome):
    # Never publish archive work onto the application's real request topics.
    config = integration_kafka_config.model_copy(deep=True)
    prefix = f"civers-test-{uuid.uuid4().hex}"
    topic_keys = ("archive_requests", "archive_status", "archive_completed", "archive_failed")
    topics = {key: f"{prefix}.{key}" for key in topic_keys}
    source = topics["archive_requests"]
    dlq = source + ".dlq"
    raw = config.transport.get_transport_config("kafka")
    config.transport.transports["kafka"] = {
        **raw,
        "topics": topics,
        "consumer_group": prefix,
        "consumer_enable_auto_commit": False,
    }
    bootstrap = raw["bootstrap_servers"]
    dispatched = []

    async def handle(command):
        dispatched.append(command)
        if outcome == "failed":
            return Result.fail("Capture failed", error_type="capture_error")
        return Result.ok(
            archive_path="/tmp/test-archive", artifacts_created=["warc", "screenshot"],
            processing_time_seconds=1.5, snapshot_id="test-snapshot",
        )

    bus = CommandBus()
    bus.register(ArchiveCommand, handle)
    transport = ArchiveKafkaTransport(config, bus)
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode(),
        key_serializer=lambda key: key.encode(),
    )
    observer = AIOKafkaConsumer(
        topics["archive_completed"], topics["archive_failed"], topics["archive_status"], dlq,
        bootstrap_servers=bootstrap, group_id=prefix + "-observer",
        auto_offset_reset="earliest", enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode()),
    )
    transport_task = None
    created = False

    async def close_transport():
        if transport_task is None:
            return
        try:
            async with asyncio.timeout(5):
                await transport.stop()
                await asyncio.shield(transport_task)
        finally:
            if not transport_task.done():
                transport_task.cancel()
            await asyncio.gather(transport_task, return_exceptions=True)

    try:
        await admin.start()
        await admin.create_topics([
            NewTopic(name, num_partitions=1, replication_factor=1)
            for name in [*topics.values(), dlq]
        ])
        created = True
        await observer.start()
        await producer.start()
        transport_task = asyncio.create_task(transport.run())
        async with asyncio.timeout(15):
            while not transport._running:
                if transport_task.done():
                    await transport_task  # Surface a boot failure immediately.
                await asyncio.sleep(0.02)

        request_id = "../bad" if outcome == "unroutable" else prefix
        payload = {
            "request_id": request_id,
            "url": "invalid-url" if outcome == "invalid" else "https://example.com/",
        }
        sent = await producer.send_and_wait(source, key=request_id, value=payload)
        expected_topic = (
            dlq if outcome == "unroutable" else
            topics["archive_completed"] if outcome == "complete" else topics["archive_failed"]
        )
        terminal, statuses = [], []
        async with asyncio.timeout(20):
            while True:
                batches = await observer.getmany(timeout_ms=250)
                for records in batches.values():
                    for record in records:
                        if record.topic == expected_topic:
                            terminal.append(record.value)
                        if record.topic == topics["archive_status"]:
                            statuses.append(record.value["status"])
                committed = await transport.consumer.committed(TopicPartition(source, sent.partition))
                if terminal and committed == sent.offset + 1:
                    if outcome not in {"complete", "failed"} or len(statuses) >= 2:
                        break
                if transport_task.done():
                    await transport_task
                    pytest.fail("Transport exited before acknowledging the request")

        assert len(terminal) == 1
        if outcome == "complete":
            assert terminal[0]["archive_path"] == "/tmp/test-archive"
            assert terminal[0]["snapshot_id"] == "test-snapshot"
            assert statuses == ["processing", "completed"]
        elif outcome == "failed":
            assert terminal[0]["error_type"] == "capture_error"
            assert statuses == ["processing", "failed"]
        elif outcome == "invalid":
            assert terminal[0]["error_type"] == "invalid_request"
            assert terminal[0]["request_id"] == request_id
            assert dispatched == []
        else:
            assert terminal[0]["payload"] == payload
            assert dispatched == []
        if outcome in {"complete", "failed"}:
            assert len(dispatched) == 1
            assert dispatched[0].request_id == request_id
            assert dispatched[0].url == payload["url"]
    finally:
        try:
            # Always close every client, even when startup or an assertion fails.
            await asyncio.gather(
                close_transport(), observer.stop(), producer.stop(), return_exceptions=True
            )
            if created:
                await admin.delete_topics([*topics.values(), dlq])
        finally:
            await admin.close()
