"""
Async Kafka Transport Service for CiVers Orchestrator.

Handles asynchronous Kafka communication for workflow coordination using aiokafka.
This service implements the CiVers Kafka Pattern:
- Centralized connection management via KafkaConnectionManager
- Standardized event publishing via EventPublisher
- Fully asynchronous message processing
- Health monitoring
"""

import asyncio
from collections.abc import Callable
from typing import Any

from configs.logging_config import get_logger
from configs.models import ConfigDataModel
from models.orchestrator_models import StepInstruction, WorkflowTransition
from orchestration_services.callback_service import CallbackService
from orchestration_services.orchestrator_service import OrchestratorService
from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
from transport_services.kafka.event_models import (
    OrchestratorCompletedEvent,
    OrchestratorFailedEvent,
    OrchestratorRequestEvent,
    OrchestratorStatusEvent,
)
from transport_services.kafka.event_publisher import EventPublisher
from transport_services.kafka.event_registry import get_event_model
from transport_services.kafka.external_events.archive_events import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
)
from transport_services.kafka.external_events.metadata_events import (
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent,
)
from transport_services.kafka.kafka_connection_manager import KafkaConnectionManager
from transport_services.transport_service_interface import TransportServiceInterface

logger = get_logger(__name__)


class KafkaTransportService(TransportServiceInterface):
    """
    Kafka transport service - handles ALL asynchronous Kafka communication.
    """

    def __init__(self, config: ConfigDataModel, orchestrator_service: OrchestratorService):
        """
        Initialize Kafka transport service.

        Args:
            config: Configuration data model
            orchestrator_service: Orchestrator for business logic
        """
        self.config = config
        self.orchestrator = orchestrator_service

        # Kafka configuration
        self.kafka_config = config.transport.kafka
        self.topics = self.kafka_config.topics
        self.running = False

        # Transport adapter (translates component → Kafka specifics)
        self.adapter = KafkaTransportAdapter(self.kafka_config)

        # Internal components
        self.connection_manager = KafkaConnectionManager(self.kafka_config)
        self.event_publisher = EventPublisher(self.connection_manager, self.topics)
        self.event_handlers: dict[str, Callable] = {}
        self.callback_service = CallbackService()

        # Reverse map: response topic → step_name (built from component_mappings config)
        self._topic_to_step_name: dict[str, str] = {
            topic: mapping.step_name
            for mapping in self.kafka_config.component_mappings.values()
            for topic in mapping.response_topics.values()
        }

        self._requests_processed = 0

    def register_handler(self, topic: str, handler: Callable) -> None:
        """Register an event handler for a specific topic."""
        self.event_handlers[topic] = handler
        logger.info(f"✅ Registered handler for topic: {topic}")

    async def start(self) -> None:
        """Start the async Kafka transport service."""
        try:
            logger.info("🚀 Starting Async Kafka transport service")

            # Setup producer
            await self.connection_manager.setup_producer()

            # Register handlers for all relevant topics
            self._register_default_handlers()

            # Setup consumer
            topics_to_consume = list(self.event_handlers.keys())
            if topics_to_consume:
                await self.connection_manager.setup_consumer(topics_to_consume)
            else:
                logger.warning("⚠️ No topics registered for consumption")

            self.running = True

            # Start consumption loop
            if self.connection_manager.consumer:
                await self._consume_loop()

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka transport service: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the service gracefully."""
        self.running = False
        logger.info("🛑 Stopping Kafka transport service...")
        await self.connection_manager.cleanup()
        logger.info("✅ Kafka transport service stopped")

    def _register_default_handlers(self) -> None:
        """Register handlers for orchestrator requests and component responses."""
        # 1. Orchestrator requests (from web interface/CLI)
        self.register_handler(
            self.topics.orchestrator_requests,
            self._handle_orchestrator_request
        )

        # 2. Archive generator responses
        archive_config = self.kafka_config.component_mappings.get("archive_generator")
        if archive_config:
            self.register_handler(
                archive_config.response_topics["success"],
                self._handle_archive_completed
            )
            self.register_handler(
                archive_config.response_topics["failure"],
                self._handle_archive_failed
            )

        # 3. Metadata extractor responses
        metadata_config = self.kafka_config.component_mappings.get("metadata_extractor")
        if metadata_config:
            self.register_handler(
                metadata_config.response_topics["success"],
                self._handle_metadata_completed
            )
            self.register_handler(
                metadata_config.response_topics["failure"],
                self._handle_metadata_failed
            )

    async def _consume_loop(self) -> None:
        """Main async consumption loop with automatic reconnection on error."""
        logger.info("📡 Starting async Kafka consumption loop")
        backoff = 1  # seconds; doubles on each consecutive failure, capped at 60

        while self.running:
            try:
                # Rebuild consumer if it was torn down by a previous error
                if self.connection_manager.consumer is None:
                    topics = list(self.event_handlers.keys())
                    logger.info(f"📡 (Re)connecting Kafka consumer for topics: {topics}")
                    await self.connection_manager.setup_consumer(topics)
                    backoff = 1  # reset after a successful connect

                async for msg in self.connection_manager.consumer:
                    if not self.running:
                        return
                    try:
                        await self._process_message(msg)
                    except Exception as e:
                        logger.error(f"❌ Error processing Kafka message: {e}", exc_info=True)

            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self.running:
                    return
                logger.error(
                    f"❌ Kafka consumption loop error: {e}. "
                    f"Reconnecting in {backoff}s...",
                    exc_info=True,
                )
                # Stop the consumer only (leave the producer intact)
                if self.connection_manager.consumer is not None:
                    try:
                        await self.connection_manager.consumer.stop()
                    except Exception:
                        pass
                    self.connection_manager.consumer = None

                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

        logger.info("📡 Kafka consumption loop stopped")

    async def _process_message(self, message: Any) -> None:
        """Process a message from the consumer."""
        topic = message.topic
        message_data = message.value

        if message_data is None:
            logger.warning(f"⚠️ Received empty message on topic {topic}")
            return

        handler = self.event_handlers.get(topic)
        if handler:
            try:
                await handler(message, message_data)
            except Exception as e:
                logger.error(f"❌ Handler error on topic {topic}: {e}", exc_info=True)
        else:
            logger.debug(f"ℹ️ No handler for topic {topic}")

    # === MESSAGE HANDLERS ===

    async def _handle_orchestrator_request(self, message: Any, message_data: dict[str, Any]):
        """Handle incoming orchestrator requests."""
        try:
            event = OrchestratorRequestEvent(**message_data)
            logger.info(f"🚀 New workflow request: {event.request_id} for {event.url}")
            self._requests_processed += 1

            # Delegate to orchestrator - start_workflow returns StepInstruction
            step_instruction = self.orchestrator.start_workflow(
                request_id=event.request_id,
                url=event.url,
                workflow_name=event.workflow_name,
                callback_url=event.callback_url,
                metadata=event.metadata
            )

            # Execute the first step
            await self._execute_step_instruction(step_instruction)
        except Exception as e:
            logger.error(f"❌ Failed to handle orchestrator request: {e}")


    async def _handle_archive_completed(self, message: Any, message_data: dict[str, Any]):
        """Handle archive.completed event."""
        try:
            event = ArchiveCompletedEvent(**message_data)
            step_name = self._topic_to_step_name[message.topic]
            logger.info(f"✅ Archive completed: {event.request_id}")

            transition = self.orchestrator.step_completed(
                request_id=event.request_id,
                step_name=step_name,
                result_data={
                    "archive_path": event.archive_path,
                    "artifacts_created": event.artifacts_created,
                    "processing_time_seconds": event.processing_time_seconds,
                    "snapshot_id": event.snapshot_id
                }
            )

            await self.execute_transition(transition)
        except Exception as e:
            logger.error(f"❌ Failed to handle archive completed: {e}")

    async def _handle_archive_failed(self, message: Any, message_data: dict[str, Any]):
        """Handle archive.failed event."""
        try:
            event = ArchiveFailedEvent(**message_data)
            step_name = self._topic_to_step_name[message.topic]
            logger.error(f"❌ Archive failed: {event.request_id}: {event.error_message}")

            transition = self.orchestrator.step_failed(
                request_id=event.request_id,
                step_name=step_name,
                error_message=event.error_message
            )

            await self.execute_transition(transition)
        except Exception as e:
            logger.error(f"❌ Failed to handle archive failure: {e}")

    async def _handle_metadata_completed(self, message: Any, message_data: dict[str, Any]):
        """Handle metadata.completed event."""
        try:
            event = MetadataExtractionCompletedEvent(**message_data)
            step_name = self._topic_to_step_name[message.topic]
            logger.info(f"✅ Metadata extraction completed: {event.request_id}")

            transition = self.orchestrator.step_completed(
                request_id=event.request_id,
                step_name=step_name,
                result_data={
                    "extracted_metadata": event.extracted_metadata,
                    "domain_used": event.domain_used,
                    "mappers_used": event.mappers_used,
                    "processing_time_seconds": event.processing_time_seconds
                }
            )

            await self.execute_transition(transition)
        except Exception as e:
            logger.error(f"❌ Failed to handle metadata completed: {e}")

    async def _handle_metadata_failed(self, message: Any, message_data: dict[str, Any]):
        """Handle metadata.failed event."""
        try:
            event = MetadataExtractionFailedEvent(**message_data)
            step_name = self._topic_to_step_name[message.topic]
            logger.error(f"❌ Metadata extraction failed: {event.request_id}: {event.error_message}")

            transition = self.orchestrator.step_failed(
                request_id=event.request_id,
                step_name=step_name,
                error_message=event.error_message
            )

            await self.execute_transition(transition)
        except Exception as e:
            logger.error(f"❌ Failed to handle metadata failure: {e}")

    # === INSTRUCTION EXECUTION ===

    async def execute_transition(self, transition: WorkflowTransition):
        """Execute a workflow transition."""
        try:
            if transition.action == "execute_step":
                await self._execute_step_instruction(transition.step_instruction)
            elif transition.action == "workflow_complete":
                await self._publish_workflow_completed(transition)
            elif transition.action == "workflow_failed":
                await self._publish_workflow_failed(transition)
            else:
                logger.error(f"❌ Unknown transition action: {transition.action}")
        except Exception as e:
            logger.error(f"❌ Failed to execute transition: {e}", exc_info=True)

    async def _execute_step_instruction(self, instruction: StepInstruction):
        """Execute a step instruction."""
        try:
            logger.info(f"📤 Executing step: {instruction.step_config.name}")
            kafka_op = self.adapter.translate_instruction(instruction)
            event_model = get_event_model(kafka_op["event_model"])

            # Create event instance
            event_data = {"request_id": instruction.request_id, "url": instruction.url}
            if instruction.input_data:
                event_data.update(instruction.input_data)
            if instruction.metadata:
                event_data["metadata"] = instruction.metadata

            event = event_model(**event_data)

            # Publish
            success = await self.event_publisher.publish_event(
                topic=kafka_op["topic"],
                key=instruction.request_id,
                event=event
            )

            if success:
                logger.info(f"✅ Published {kafka_op['event_model']} to {kafka_op['topic']}")
                wf = instruction.workflow_instance
                workflow = self.orchestrator.resolver.get_workflow(wf.workflow_name)
                await self._publish_status_update(
                    request_id=instruction.request_id,
                    url=instruction.url,
                    workflow_name=wf.workflow_name,
                    current_step=instruction.step_config.name,
                    status="in_progress",
                    completed_steps=list(wf.completed_steps),
                    workflow_steps=[s.name for s in workflow.steps]
                )
        except Exception as e:
            logger.error(f"❌ Failed to execute step instruction: {e}")

    async def _publish_workflow_completed(self, transition: WorkflowTransition):
        """Publish workflow completion."""
        try:
            wf = transition.workflow_instance
            workflow = self.orchestrator.resolver.get_workflow(wf.workflow_name)
            event = OrchestratorCompletedEvent(
                request_id=wf.request_id,
                url=wf.url,
                workflow_name=wf.workflow_name,
                completed_steps=list(wf.completed_steps),
                workflow_steps=[s.name for s in workflow.steps],
                processing_time_seconds=wf.processing_time_seconds or 0.0,
                step_results=wf.step_results
            )

            success = await self.event_publisher.publish_event(
                topic=self.topics.orchestrator_completed,
                key=wf.request_id,
                event=event
            )

            if success:
                logger.info(f"✅ Workflow completed: {wf.request_id}")
                if wf.callback_url:
                    callback_payload = event.model_dump()
                    callback_payload["status"] = "completed"
                    await self.callback_service.send_callback(
                        wf.callback_url, callback_payload, wf.request_id
                    )
        except Exception as e:
            logger.error(f"❌ Failed to publish workflow completion: {e}")

    async def _publish_workflow_failed(self, transition: WorkflowTransition):
        """Publish workflow failure."""
        try:
            wf = transition.workflow_instance
            workflow = self.orchestrator.resolver.get_workflow(wf.workflow_name)
            event = OrchestratorFailedEvent(
                request_id=wf.request_id,
                url=wf.url,
                workflow_name=wf.workflow_name,
                failed_step=transition.failed_step,
                error_message=transition.error_message,
                completed_steps=list(wf.completed_steps),
                workflow_steps=[s.name for s in workflow.steps]
            )

            success = await self.event_publisher.publish_event(
                topic=self.topics.orchestrator_failed,
                key=wf.request_id,
                event=event
            )

            if success:
                logger.error(f"❌ Workflow failed: {wf.request_id}")
                if wf.callback_url:
                    callback_payload = event.model_dump()
                    callback_payload["status"] = "failed"
                    await self.callback_service.send_callback(
                        wf.callback_url, callback_payload, wf.request_id
                    )
        except Exception as e:
            logger.error(f"❌ Failed to publish workflow failure: {e}")

    async def _publish_status_update(self, **kwargs):
        """Publish status update."""
        try:
            event = OrchestratorStatusEvent(**kwargs)
            success = await self.event_publisher.publish_event(
                topic=self.topics.orchestrator_status,
                key=kwargs["request_id"],
                event=event
            )
            if success:
                logger.info(f"📊 Status update: {kwargs['request_id']} [{kwargs['status']}]")
                # Handle callbacks for status updates if needed
                wf = self.orchestrator.get_workflow_state(kwargs["request_id"])
                if wf and wf.callback_url:
                    await self.callback_service.send_callback(
                        wf.callback_url, event.model_dump(), kwargs["request_id"]
                    )
        except Exception as e:
            logger.error(f"❌ Failed to publish status update: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        try:
            producer_ready = self.connection_manager.producer is not None
            consumer_ready = self.connection_manager.consumer is not None
            return {
                "healthy": self.running and producer_ready,
                "running": self.running,
                "details": {
                    "service": "kafka_transport",
                    "running": self.running,
                    "producer_ready": producer_ready,
                    "consumer_ready": consumer_ready,
                    "registered_topics": list(self.event_handlers.keys()),
                    "requests_processed": self._requests_processed,
                }
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def send_response(self, destination: str, message: dict[str, Any], **kwargs) -> bool:
        """Generic response sender."""
        return await self.event_publisher.publish_dict(destination, kwargs.get("key"), message)

    def get_transport_info(self) -> dict[str, Any]:
        """Info about transport."""
        return {
            "transport_type": "KafkaTransportService",
            "kafka_config": {
                "bootstrap_servers": self.kafka_config.bootstrap_servers,
                "consumer_group": self.kafka_config.consumer.group_id,
            },
            "status": {
                "running": self.running,
                "producer_ready": self.connection_manager.producer is not None,
                "consumer_ready": self.connection_manager.consumer is not None,
            }
        }
