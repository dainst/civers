"""Shared aiokafka transport for CiVers components."""
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from civers_common.configs.models import BaseKafkaConfig
from civers_common.messaging import CommandBus
from .base import Transport

logger = logging.getLogger(__name__)
DEFAULT_MAX_POLL_INTERVAL_MS = 600_000

@dataclass(frozen=True, slots=True)
class InboundMessage:
    destination: str
    payload: Any
    key: str | None
    raw: Any

KafkaHandler = Callable[[InboundMessage], Awaitable[None]]

class KafkaTransport(Transport):
    """Kafka mechanics only; components register handlers and dispatch commands."""
    dead_letter_suffix: str | None = ".dlq"

    def __init__(self, bus: CommandBus, kafka_config: BaseKafkaConfig):
        super().__init__(bus)
        self.kafka_config = kafka_config
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self._handlers: dict[str, KafkaHandler] = {}
        self._running = False
        self._stop_requested = False
        self._handlers_registered = False

    def register_handlers(self) -> None:
        """Override in a component transport."""
        return None

    def register_handler(self, destination_key: str, handler: KafkaHandler) -> None:
        destination = self.kafka_config.topics.get(destination_key)
        if not destination:
            raise ValueError(
                f"Kafka topic mapping is missing logical destination {destination_key!r}"
            )
        self._handlers[destination] = handler

    async def run(self) -> int:
        try:
            if not self._handlers_registered:
                self.register_handlers()
                self._handlers_registered = True
            if not self._handlers:
                raise RuntimeError("Kafka transport has no registered handlers")

            await self._start_producer()
            await self._start_consumer(list(self._handlers))
            if self._stop_requested:
                return 0
            self._running = True
            await self._consume()
            return 0
        finally:
            self._running = False
            await self._close()

    async def stop(self) -> None:
        """Stop intake; run() closes clients after the active handler commits."""
        self._stop_requested = True
        self._running = False

    async def _start_producer(self) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_config.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
            key_serializer=lambda key: key.encode("utf-8") if key else None,
            acks=self.kafka_config.producer_acks,
            request_timeout_ms=self.kafka_config.producer_request_timeout_ms,
            retry_backoff_ms=self.kafka_config.producer_retry_backoff_ms,
            **(self.kafka_config.producer or {}),
        )
        await self.producer.start()

    async def _start_consumer(self, topics: list[str]) -> None:
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_config.bootstrap_servers,
            group_id=self.kafka_config.consumer_group,
            value_deserializer=self._deserialize,
            key_deserializer=lambda key: key.decode("utf-8") if key else None,
            auto_offset_reset=self.kafka_config.consumer_auto_offset_reset,
            enable_auto_commit=self.kafka_config.consumer_enable_auto_commit,
            request_timeout_ms=self.kafka_config.consumer_request_timeout_ms,
            max_poll_interval_ms=self.kafka_config.consumer_max_poll_interval_ms,
            **(self.kafka_config.consumer or {}),
        )
        await self.consumer.start()

    async def _consume(self) -> None:
        if self.consumer is None:
            raise RuntimeError("Kafka consumer is not initialized")

        while self._running:
            batches = await self.consumer.getmany(timeout_ms=500, max_records=1)
            for records in batches.values():
                if not self._running:
                    return
                record = records[0]
                message = InboundMessage(
                    destination=record.topic,
                    payload=record.value,
                    key=record.key,
                    raw=record,
                )
                await self._dispatch(message)

    async def _dispatch(self, message: InboundMessage) -> None:
        handler = self._handlers.get(message.destination)
        if handler is None:
            logger.warning("No Kafka handler registered for %s", message.destination)
            return

        try:
            if message.payload is None:
                raise ValueError("Kafka message payload is empty or invalid JSON")
            await handler(message)
        except Exception as exc:
            logger.exception("Kafka handler failed for %s", message.destination)
            await self._dead_letter(message, exc)
            return

        await self._ack(message)

    async def publish(self, destination_key: str, key: str | None, payload: Any) -> None:
        destination = self.kafka_config.topics.get(destination_key)
        if not destination:
            raise ValueError(
                f"Kafka topic mapping is missing logical destination {destination_key!r}"
            )
        await self.publish_to(destination, key, payload)

    async def publish_to(self, destination: str, key: str | None, payload: Any) -> None:
        if self.producer is None:
            raise RuntimeError("Kafka producer is not initialized")
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        await self.producer.send_and_wait(topic=destination, key=key, value=payload)

    async def _ack(self, message: InboundMessage) -> None:
        if self.consumer is None or message.raw is None:
            return
        record = message.raw
        tp = TopicPartition(record.topic, record.partition)
        await self.consumer.commit({tp: record.offset + 1})

    async def _dead_letter(self, message: InboundMessage, error: Exception) -> None:
        if self.dead_letter_suffix is None:
            raise RuntimeError("DLQ disabled; stopping before an unresolved request") from error

        destination = f"{message.destination}{self.dead_letter_suffix}"
        envelope = {
            "source_destination": message.destination,
            "key": message.key,
            "error": str(error),
            "error_type": type(error).__name__,
            "payload": message.payload,
        }
        # Propagate publication failures. Processing a later record could commit
        # past this unresolved request because Kafka offsets are cumulative.
        await self.publish_to(destination, message.key, envelope)
        await self._ack(message)

    async def _close(self) -> None:
        if self.consumer is not None:
            try:
                await self.consumer.stop()
            except Exception:
                logger.exception("Error stopping Kafka consumer")
            finally:
                self.consumer = None

        if self.producer is not None:
            try:
                await self.producer.stop()
            except Exception:
                logger.exception("Error stopping Kafka producer")
            finally:
                self.producer = None

    @staticmethod
    def _deserialize(value: bytes | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Received invalid JSON Kafka message")
            return None

    def info(self) -> dict[str, Any]:
        return {
            "type": "kafka",
            "bootstrap_servers": self.kafka_config.bootstrap_servers,
            "consumer_group": self.kafka_config.consumer_group,
        }
