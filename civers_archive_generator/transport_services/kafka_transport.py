"""Convert Kafka archive requests to commands and publish result events.

The shared KafkaTransport manages Kafka clients, commits and dead-letter messages.
"""

import logging
from typing import Any, ClassVar

from civers_common import CommandBus, ConfigurationError, ResultStatus, is_valid_request_id
from civers_common.configs.models import BaseKafkaConfig
from civers_common.transport.kafka import InboundMessage, KafkaTransport

from domain.commands import ArchiveCommand

from .event_models import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
    ArchiveRequestEvent,
    ArchiveStatusEvent,
)

logger = logging.getLogger(__name__)

_INVALID_REQUEST_URL = "https://invalid.request/"


class ArchiveKafkaTransport(KafkaTransport):
    """Kafka delivery adapter for archive requests."""

    config_model: ClassVar[type[BaseKafkaConfig]] = BaseKafkaConfig

    def __init__(self, config: Any, bus: CommandBus):
        self.config = config

        raw = config.transport.get_transport_config("kafka")
        if not raw:
            raise ConfigurationError(
                "Kafka transport is enabled but transport.transports.kafka is missing"
            )

        kafka_config = self.config_model.model_validate(raw)
        for name in ("archive_requests", "archive_completed", "archive_failed"):
            if not kafka_config.topics.get(name):
                raise ConfigurationError(f"Missing Kafka topic: {name}")
        super().__init__(bus=bus, kafka_config=kafka_config)

    def register_handlers(self) -> None:
        """Subscribe the Archive Generator to archive request messages."""
        self.register_handler(
            "archive_requests",
            self._handle_archive_request,
        )

    async def _handle_archive_request(self, message: InboundMessage) -> None:
        """Validate one wire request, dispatch it, and publish its outcome."""
        payload = message.payload

        if not isinstance(payload, dict):
            # Raising lets the shared Kafka transport send the raw message to the DLQ.
            raise ValueError(
                f"Archive request payload must be an object, got {type(payload).__name__}"
            )

        try:
            event = ArchiveRequestEvent.model_validate(payload)
        except Exception as exc:
            handled = await self._publish_invalid_request(payload, exc)
            if handled:
                # Returning after the failure event lets KafkaTransport commit this request.
                return

            # Without a valid request ID, send the original payload to the dead-letter topic.
            raise ValueError(f"Invalid archive request payload: {exc}") from exc

        logger.info(
            "Processing archive request %s for %s",
            event.request_id,
            event.url,
        )

        await self._publish_status_best_effort(
            ArchiveStatusEvent(
                request_id=event.request_id,
                url=event.url,
                status="processing",
                message=f"Archive generation started for {event.url}",
            )
        )

        result = await self.bus.dispatch(
            ArchiveCommand(
                request_id=event.request_id,
                url=event.url,
            )
        )

        if result.success_status is ResultStatus.FAILED:
            await self._publish_failed(event, result)
        else:
            await self._publish_completed(event, result)

    async def _publish_completed(self, event: ArchiveRequestEvent, result: Any) -> None:
        """Publish the required completion event, then an optional status update."""
        data = result.data or {}

        completed = ArchiveCompletedEvent(
            request_id=event.request_id,
            url=event.url,
            archive_path=data["archive_path"],
            artifacts_created=data["artifacts_created"],
            processing_time_seconds=data["processing_time_seconds"],
            snapshot_id=data.get("snapshot_id"),
            status=result.success_status.value,
            failed_artifacts=data.get("failed_artifacts", []),
            missing_artifacts=data.get("missing_artifacts", []),
            skipped_generators=data.get("skipped_generators", []),
        )

        # Let publication failures reach KafkaTransport for dead-letter handling.
        await self.publish(
            "archive_completed",
            event.request_id,
            completed,
        )

        await self._publish_status_best_effort(
            ArchiveStatusEvent(
                request_id=event.request_id,
                url=event.url,
                status="completed",
                message=(
                    f"Archive {result.success_status.value} in "
                    f"{data['processing_time_seconds']:.1f}s"
                ),
            )
        )

        logger.info("Archive request %s finished", event.request_id)

    async def _publish_failed(self, event: ArchiveRequestEvent, result: Any) -> None:
        """Publish the required failure event, then an optional status update."""
        data = result.data or {}
        error_message = result.error or "Unknown error"

        failed = ArchiveFailedEvent(
            request_id=event.request_id,
            url=event.url,
            error_message=error_message,
            error_type=result.error_type,
            archive_path=data.get("archive_path"),
            artifacts_created=data.get("artifacts_created", []),
            failed_artifacts=data.get("failed_artifacts", []),
            missing_artifacts=data.get("missing_artifacts", []),
            processing_time_seconds=data.get("processing_time_seconds"),
        )

        await self.publish(
            "archive_failed",
            event.request_id,
            failed,
        )

        await self._publish_status_best_effort(
            ArchiveStatusEvent(
                request_id=event.request_id,
                url=event.url,
                status="failed",
                message=f"Archive failed: {error_message}",
            )
        )

        logger.error(
            "Archive request %s failed: %s",
            event.request_id,
            error_message,
        )

    async def _publish_status_best_effort(self, event: ArchiveStatusEvent) -> None:
        """Publish an informational status update without failing the request."""
        try:
            await self.publish(
                "archive_status",
                event.request_id,
                event,
            )
        except Exception:
            logger.warning(
                "Could not publish archive status for request %s",
                event.request_id,
                exc_info=True,
            )

    async def _publish_invalid_request(
        self,
        payload: dict[str, Any],
        error: Exception,
    ) -> bool:
        """Publish a failure event when the invalid request still has a valid ID.

        Return True after publication succeeds.
        """
        request_id = payload.get("request_id")
        if not is_valid_request_id(request_id):
            return False

        raw_url = payload.get("url")

        # Use a placeholder URL when the original fails event validation.
        candidate_urls = []
        if isinstance(raw_url, str):
            candidate_urls.append(raw_url)
        candidate_urls.append(_INVALID_REQUEST_URL)

        failed_event: ArchiveFailedEvent | None = None
        for url in candidate_urls:
            try:
                failed_event = ArchiveFailedEvent(
                    request_id=request_id,
                    url=url,
                    error_message=f"Invalid archive request payload: {error}",
                    error_type="invalid_request",
                )
                break
            except Exception:
                continue

        if failed_event is None:
            return False

        await self.publish(
            "archive_failed",
            request_id,
            failed_event,
        )
        return True
