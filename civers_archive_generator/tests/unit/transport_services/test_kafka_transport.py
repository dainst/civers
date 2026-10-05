from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("aiokafka")

from civers_common.transport.kafka import InboundMessage
from transport_services.kafka_transport import ArchiveKafkaTransport

from civers_common import ResultStatus


class TransportConfig:
    def __init__(self, kafka):
        self.kafka = kafka

    def get_transport_config(self, name):
        assert name == "kafka"
        return self.kafka


def app_config(kafka=None):
    return SimpleNamespace(transport=TransportConfig(kafka))


def kafka_config():
    return SimpleNamespace(
        bootstrap_servers=["kafka:9092"],
        consumer_group="archive-generator",
        topics={
            "archive_requests": "archive.requests",
            "archive_status": "archive.status",
            "archive_completed": "archive.completed",
            "archive_failed": "archive.failed",
        },
        producer_acks="all",
        producer_request_timeout_ms=40000,
        producer_retry_backoff_ms=100,
        consumer_auto_offset_reset="earliest",
        consumer_request_timeout_ms=40000,
        max_poll_interval_ms=600000,
    )


def message(payload):
    return InboundMessage(
        destination="archive.requests",
        payload=payload,
        key=payload.get("request_id") if isinstance(payload, dict) else None,
        raw=object(),
    )


def successful_result(status_value="complete"):
    return SimpleNamespace(
        success_status=SimpleNamespace(value=status_value),
        data={
            "archive_path": "/archive/r1",
            "artifacts_created": ["warc", "dom-snapshot"],
            "processing_time_seconds": 2.5,
            "snapshot_id": "snapshot-1",
            "failed_artifacts": [],
            "missing_artifacts": [],
            "skipped_generators": [],
        },
        error=None,
        error_type=None,
    )


def failed_result():
    return SimpleNamespace(
        success_status=ResultStatus.FAILED,
        data={
            "archive_path": "/archive/r1",
            "artifacts_created": [],
            "failed_artifacts": ["warc"],
            "missing_artifacts": [],
            "processing_time_seconds": 1.5,
        },
        error="WARC failed",
        error_type="artifact_error",
    )


@pytest.fixture
def transport(monkeypatch):
    validated = kafka_config()
    model_validate = MagicMock(return_value=validated)
    monkeypatch.setattr(
        ArchiveKafkaTransport.config_model,
        "model_validate",
        model_validate,
    )

    bus = SimpleNamespace(dispatch=AsyncMock())
    instance = ArchiveKafkaTransport(
        config=app_config({"bootstrap_servers": ["kafka:9092"]}),
        bus=bus,
    )
    instance.publish = AsyncMock()
    return instance


def test_constructor_validates_kafka_config(monkeypatch):
    validated = kafka_config()
    model_validate = MagicMock(return_value=validated)
    monkeypatch.setattr(
        ArchiveKafkaTransport.config_model,
        "model_validate",
        model_validate,
    )

    raw = {"bootstrap_servers": ["kafka:9092"]}
    bus = object()

    transport = ArchiveKafkaTransport(
        config=app_config(raw),
        bus=bus,
    )

    model_validate.assert_called_once_with(raw)
    assert transport.kafka_config is validated
    assert transport.bus is bus


def test_constructor_requires_kafka_config():
    with pytest.raises(Exception, match="Kafka transport is enabled"):
        ArchiveKafkaTransport(
            config=app_config(None),
            bus=object(),
        )


def test_register_handlers_maps_archive_requests(transport):
    transport.register_handlers()

    assert "archive.requests" in transport._handlers
    assert transport._handlers["archive.requests"] == transport._handle_archive_request


@pytest.mark.asyncio
async def test_success_dispatches_command_and_publishes_completion(transport):
    transport.bus.dispatch.return_value = successful_result()

    await transport._handle_archive_request(
        message(
            {
                "request_id": "r1",
                "url": "https://example.org",
            }
        )
    )

    command = transport.bus.dispatch.await_args.args[0]
    assert command.request_id == "r1"
    assert command.url == "https://example.org"

    calls = transport.publish.await_args_list

    # processing status
    assert calls[0].args[0] == "archive_status"
    assert calls[0].args[1] == "r1"
    assert calls[0].args[2].status == "processing"

    # required terminal event
    assert calls[1].args[0] == "archive_completed"
    completed = calls[1].args[2]
    assert completed.archive_path == "/archive/r1"
    assert completed.artifacts_created == ["warc", "dom-snapshot"]
    assert completed.processing_time_seconds == 2.5
    assert completed.status == "complete"

    # final informational status
    assert calls[2].args[0] == "archive_status"
    assert calls[2].args[2].status == "completed"


@pytest.mark.asyncio
async def test_partial_result_uses_partial_completion_status(transport):
    transport.bus.dispatch.return_value = successful_result("partial")

    await transport._handle_archive_request(
        message(
            {
                "request_id": "r1",
                "url": "https://example.org",
            }
        )
    )

    completed = transport.publish.await_args_list[1].args[2]
    assert completed.status == "partial"


@pytest.mark.asyncio
async def test_failure_publishes_archive_failed(transport):
    transport.bus.dispatch.return_value = failed_result()

    await transport._handle_archive_request(
        message(
            {
                "request_id": "r1",
                "url": "https://example.org",
            }
        )
    )

    calls = transport.publish.await_args_list

    assert calls[1].args[0] == "archive_failed"
    failed = calls[1].args[2]
    assert failed.error_message == "WARC failed"
    assert failed.error_type == "artifact_error"
    assert failed.failed_artifacts == ["warc"]

    assert calls[2].args[0] == "archive_status"
    assert calls[2].args[2].status == "failed"


@pytest.mark.asyncio
async def test_invalid_request_with_routable_id_publishes_terminal_failure(transport):
    await transport._handle_archive_request(
        message(
            {
                "request_id": "r1",
                "url": "not-a-url",
            }
        )
    )

    transport.bus.dispatch.assert_not_awaited()

    transport.publish.assert_awaited_once()
    destination_key, key, failed = transport.publish.await_args.args

    assert destination_key == "archive_failed"
    assert key == "r1"
    assert failed.error_type == "invalid_request"
    assert failed.url == "https://invalid.request/"


@pytest.mark.asyncio
async def test_invalid_request_without_routable_id_raises_for_common_dlq(transport):
    with pytest.raises(ValueError, match="Invalid archive request payload"):
        await transport._handle_archive_request(
            message(
                {
                    "request_id": "../bad",
                    "url": "not-a-url",
                }
            )
        )

    transport.bus.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_dict_payload_raises_for_common_dlq(transport):
    with pytest.raises(ValueError, match="must be an object"):
        await transport._handle_archive_request(
            InboundMessage(
                destination="archive.requests",
                payload=["not", "an", "object"],
                key=None,
                raw=object(),
            )
        )


@pytest.mark.asyncio
async def test_status_publish_failure_does_not_fail_successful_request(transport):
    transport.bus.dispatch.return_value = successful_result()

    async def publish(destination_key, key, payload):
        if destination_key == "archive_status":
            raise RuntimeError("status topic unavailable")

    transport.publish.side_effect = publish

    await transport._handle_archive_request(
        message(
            {
                "request_id": "r1",
                "url": "https://example.org",
            }
        )
    )

    terminal_calls = [
        call
        for call in transport.publish.await_args_list
        if call.args[0] == "archive_completed"
    ]
    assert len(terminal_calls) == 1


@pytest.mark.asyncio
async def test_terminal_publish_failure_propagates_for_common_dlq(transport):
    transport.bus.dispatch.return_value = successful_result()

    async def publish(destination_key, key, payload):
        if destination_key == "archive_completed":
            raise RuntimeError("terminal topic unavailable")

    transport.publish.side_effect = publish

    with pytest.raises(RuntimeError, match="terminal topic unavailable"):
        await transport._handle_archive_request(
            message(
                {
                    "request_id": "r1",
                    "url": "https://example.org",
                }
            )
        )


@pytest.mark.parametrize(
    "topic", ["archive_requests", "archive_completed", "archive_failed"]
)
def test_missing_required_topic_fails_at_startup(topic):
    raw = {
        "bootstrap_servers": "localhost:29092",
        "topics": dict(kafka_config().topics),
    }
    del raw["topics"][topic]
    with pytest.raises(Exception, match=f"Missing Kafka topic: {topic}"):
        ArchiveKafkaTransport(app_config(raw), object())
