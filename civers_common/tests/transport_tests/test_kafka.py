from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("aiokafka")

from civers_common.transport.kafka import (
    DEFAULT_MAX_POLL_INTERVAL_MS,
    InboundMessage,
    KafkaTransport,
)
from civers_common.configs.models import BaseKafkaConfig


def kafka_config(**overrides):
    values = {
        "bootstrap_servers": ["kafka:9092"],
        "consumer_group": "archive-generator",
        "topics": {
            "archive_requests": "archive.requests",
            "archive_completed": "archive.completed",
        },
        "producer_acks": "all",
        "producer_request_timeout_ms": 40000,
        "producer_retry_backoff_ms": 100,
        "consumer_auto_offset_reset": "earliest",
        "consumer_request_timeout_ms": 40000,
        "consumer_max_poll_interval_ms": 600000,
        "consumer_enable_auto_commit": False,
        "consumer": None,
        "producer": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DummyKafkaTransport(KafkaTransport):
    def __init__(self, *, handler=None, config=None):
        super().__init__(
            bus=object(),
            kafka_config=config or kafka_config(),
        )
        self.handler = handler or AsyncMock()

    def register_handlers(self) -> None:
        self.register_handler("archive_requests", self.handler)


def inbound(payload=None):
    record = SimpleNamespace(
        topic="archive.requests",
        partition=2,
        offset=15,
    )
    return InboundMessage(
        destination="archive.requests",
        payload={"request_id": "r1"} if payload is None else payload,
        key="r1",
        raw=record,
    )


def test_register_handler_resolves_logical_destination():
    handler = AsyncMock()
    transport = DummyKafkaTransport(handler=handler)

    transport.register_handlers()

    assert transport._handlers == {
        "archive.requests": handler,
    }


def test_register_handler_rejects_unknown_logical_destination():
    transport = DummyKafkaTransport()

    with pytest.raises(ValueError, match="missing logical destination"):
        transport.register_handler("does_not_exist", AsyncMock())


@pytest.mark.asyncio
async def test_dispatch_calls_handler_then_acks():
    handler = AsyncMock()
    transport = DummyKafkaTransport(handler=handler)
    transport.register_handlers()
    transport._ack = AsyncMock()

    message = inbound()

    await transport._dispatch(message)

    handler.assert_awaited_once_with(message)
    transport._ack.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_handler_failure_goes_to_dlq_and_is_not_directly_acked():
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    transport = DummyKafkaTransport(handler=handler)
    transport.register_handlers()

    transport._dead_letter = AsyncMock()
    transport._ack = AsyncMock()

    message = inbound()

    await transport._dispatch(message)

    transport._dead_letter.assert_awaited_once()
    transport._ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_json_payload_goes_to_dlq():
    transport = DummyKafkaTransport()
    transport.register_handlers()

    transport._dead_letter = AsyncMock()
    transport._ack = AsyncMock()

    message = inbound(payload=None)
    # Explicitly model deserialization failure.
    message = InboundMessage(
        destination=message.destination,
        payload=None,
        key=message.key,
        raw=message.raw,
    )

    await transport._dispatch(message)

    transport._dead_letter.assert_awaited_once()
    transport._ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_dead_letter_publishes_envelope_then_acks():
    transport = DummyKafkaTransport()
    transport.publish_to = AsyncMock()
    transport._ack = AsyncMock()

    message = inbound()
    error = ValueError("bad payload")

    await transport._dead_letter(message, error)

    transport.publish_to.assert_awaited_once()

    destination, key, envelope = transport.publish_to.await_args.args
    assert destination == "archive.requests.dlq"
    assert key == "r1"
    assert envelope["source_destination"] == "archive.requests"
    assert envelope["error"] == "bad payload"
    assert envelope["error_type"] == "ValueError"
    assert envelope["payload"] == {"request_id": "r1"}

    transport._ack.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_dlq_publish_failure_leaves_message_unacked():
    transport = DummyKafkaTransport()
    transport.publish_to = AsyncMock(side_effect=RuntimeError("Kafka unavailable"))
    transport._ack = AsyncMock()

    with pytest.raises(RuntimeError, match="Kafka unavailable"):
        await transport._dead_letter(inbound(), RuntimeError("handler failed"))

    transport._ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_resolves_logical_topic():
    transport = DummyKafkaTransport()
    transport.publish_to = AsyncMock()

    payload = {"request_id": "r1"}

    await transport.publish("archive_completed", "r1", payload)

    transport.publish_to.assert_awaited_once_with(
        "archive.completed",
        "r1",
        payload,
    )


@pytest.mark.asyncio
async def test_publish_to_serializes_pydantic_like_model():
    transport = DummyKafkaTransport()

    producer = MagicMock()
    producer.send_and_wait = AsyncMock()
    transport.producer = producer

    model = MagicMock()
    model.model_dump.return_value = {"request_id": "r1"}

    await transport.publish_to("archive.completed", "r1", model)

    producer.send_and_wait.assert_awaited_once_with(
        topic="archive.completed",
        key="r1",
        value={"request_id": "r1"},
    )


@pytest.mark.asyncio
async def test_ack_commits_next_offset():
    transport = DummyKafkaTransport()

    consumer = MagicMock()
    consumer.commit = AsyncMock()
    transport.consumer = consumer

    message = inbound()

    await transport._ack(message)

    committed = consumer.commit.await_args.args[0]
    assert list(committed.values()) == [16]

    partition = next(iter(committed))
    assert partition.topic == "archive.requests"
    assert partition.partition == 2


@pytest.mark.asyncio
async def test_run_registers_handlers_and_owns_lifecycle():
    transport = DummyKafkaTransport()

    transport._start_producer = AsyncMock()
    transport._start_consumer = AsyncMock()
    transport._consume = AsyncMock()
    transport._close = AsyncMock()

    result = await transport.run()

    assert result == 0
    assert transport._handlers_registered is True
    transport._start_producer.assert_awaited_once()
    transport._start_consumer.assert_awaited_once_with(["archive.requests"])
    transport._consume.assert_awaited_once()
    transport._close.assert_awaited_once()
    assert transport._running is False


@pytest.mark.asyncio
async def test_run_closes_on_failure():
    transport = DummyKafkaTransport()

    transport._start_producer = AsyncMock()
    transport._start_consumer = AsyncMock()
    transport._consume = AsyncMock(side_effect=RuntimeError("consumer failed"))
    transport._close = AsyncMock()

    with pytest.raises(RuntimeError, match="consumer failed"):
        await transport.run()

    transport._close.assert_awaited_once()
    assert transport._running is False


@pytest.mark.asyncio
async def test_stop_preserves_clients_until_handler_finishes():
    transport = DummyKafkaTransport()

    consumer = MagicMock()
    consumer.stop = AsyncMock()
    producer = MagicMock()

    transport.consumer = consumer
    transport.producer = producer
    transport._running = True

    await transport.stop()

    consumer.stop.assert_not_awaited()
    assert transport.consumer is consumer
    assert transport.producer is producer
    assert transport._running is False


@pytest.mark.asyncio
async def test_failed_dlq_prevents_consuming_and_committing_later_record():
    handler = AsyncMock(side_effect=ValueError("bad request"))
    transport = DummyKafkaTransport(handler=handler)
    transport.register_handlers()
    transport._running = True
    first = SimpleNamespace(topic="archive.requests", partition=0, offset=1, value={}, key="r1")
    second = SimpleNamespace(topic="archive.requests", partition=0, offset=2, value={}, key="r2")
    transport.consumer = SimpleNamespace(
        getmany=AsyncMock(side_effect=[{0: [first]}, {0: [second]}]),
        commit=AsyncMock(),
    )
    transport.publish_to = AsyncMock(side_effect=RuntimeError("broker unavailable"))
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await transport._consume()
    transport.consumer.commit.assert_not_awaited()
    assert transport.consumer.getmany.await_count == 1


@pytest.mark.asyncio
async def test_shutdown_during_handler_commits_before_closing_clients():
    transport = DummyKafkaTransport()
    transport._running = True
    transport.consumer = SimpleNamespace(commit=AsyncMock(), stop=AsyncMock())
    transport.producer = SimpleNamespace(stop=AsyncMock())

    async def finish(message):
        await transport.stop()

    transport.handler = finish
    transport.register_handlers()
    consumer = transport.consumer
    await transport._dispatch(inbound())
    consumer.commit.assert_awaited_once()
    consumer.stop.assert_not_awaited()
    await transport._close()
    consumer.stop.assert_awaited_once()


def test_deserialize():
    assert KafkaTransport._deserialize(b'{"a": 1}') == {"a": 1}
    assert KafkaTransport._deserialize(None) is None
    assert KafkaTransport._deserialize(b"not-json") is None


def test_default_poll_interval_is_ten_minutes():
    assert DEFAULT_MAX_POLL_INTERVAL_MS == 600_000


@pytest.mark.asyncio
async def test_real_config_forwards_explicit_fields_and_component_extensions():
    config = BaseKafkaConfig(
        bootstrap_servers="kafka:9092", consumer_group="archives",
        topics={"archive_requests": "archive.requests"},
        producer_acks="all", producer_request_timeout_ms=60000,
        consumer_max_poll_interval_ms=900000,
        consumer_request_timeout_ms=60000,
        consumer={"session_timeout_ms": 45000, "check_crcs": False},
        producer={"compression_type": "gzip", "linger_ms": 25},
    )
    transport = DummyKafkaTransport(config=config)
    with patch("civers_common.transport.kafka.AIOKafkaProducer") as producer, \
         patch("civers_common.transport.kafka.AIOKafkaConsumer") as consumer:
        producer.return_value.start = AsyncMock()
        consumer.return_value.start = AsyncMock()
        await transport._start_producer()
        await transport._start_consumer(["archive.requests"])
        assert producer.call_args.kwargs["acks"] == "all"
        assert producer.call_args.kwargs["request_timeout_ms"] == 60000
        assert producer.call_args.kwargs["compression_type"] == "gzip"
        assert producer.call_args.kwargs["linger_ms"] == 25
        assert consumer.call_args.kwargs["max_poll_interval_ms"] == 900000
        assert consumer.call_args.kwargs["session_timeout_ms"] == 45000
        assert consumer.call_args.kwargs["check_crcs"] is False
        assert consumer.call_args.kwargs["enable_auto_commit"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("section,options", [
    ("producer", {"acks": "all"}),
    ("producer", {"value_serializer": "override"}),
    ("consumer", {"max_poll_interval_ms": 900000}),
    ("consumer", {"group_id": "other-group"}),
])
async def test_extensions_cannot_duplicate_explicit_arguments(section, options):
    config = BaseKafkaConfig(
        bootstrap_servers="kafka:9092", topics={"archive_requests": "archive.requests"},
        **{section: options},
    )
    transport = DummyKafkaTransport(config=config)
    with pytest.raises(TypeError, match="multiple values"):
        if section == "producer":
            await transport._start_producer()
        else:
            await transport._start_consumer(["archive.requests"])


@pytest.mark.asyncio
@pytest.mark.parametrize("section,options", [
    ("producer", {"retries": 3}),
    ("consumer", {"unsupported_option": True}),
])
async def test_aiokafka_rejects_unsupported_extension_arguments(section, options):
    config = BaseKafkaConfig(
        bootstrap_servers="kafka:9092", topics={"archive_requests": "archive.requests"},
        **{section: options},
    )
    transport = DummyKafkaTransport(config=config)
    with pytest.raises(TypeError, match="unexpected keyword"):
        if section == "producer":
            await transport._start_producer()
        else:
            await transport._start_consumer(["archive.requests"])


@pytest.mark.asyncio
async def test_stop_during_connection_does_not_resume_intake():
    import asyncio
    transport = DummyKafkaTransport()
    connecting = asyncio.Event()
    connected = asyncio.Event()
    async def connect(topics):
        connecting.set()
        await connected.wait()
    transport._start_producer = AsyncMock()
    transport._start_consumer = connect
    transport._consume = AsyncMock()
    transport._close = AsyncMock()
    task = asyncio.create_task(transport.run())
    await connecting.wait()
    await transport.stop()
    connected.set()
    assert await task == 0
    transport._consume.assert_not_called()
    transport._close.assert_awaited_once()
