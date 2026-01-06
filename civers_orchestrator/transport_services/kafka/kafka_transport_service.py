"""Refactored Kafka Transport Service for CiVers Orchestrator.

This service handles ALL Kafka communication with NO business logic.
It executes instructions from OrchestratorService by creating and publishing events.

Key Principles:
- NO business logic or workflow knowledge
- Executes instructions from orchestrator
- Creates events based on instructions
- Delegates all orchestration to OrchestratorService
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any, Type, Optional

from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel

from configs.logging_config import get_logger
from configs.models import ConfigDataModel
from models.orchestrator_models import StepInstruction, WorkflowTransition
from orchestration_services.orchestrator_service import OrchestratorService
from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
from transport_services.kafka.event_publisher import EventPublisher
from transport_services.kafka.event_registry import get_event_model
from orchestration_services.callback_service import CallbackService
from transport_services.kafka.event_models import (
    OrchestratorRequestEvent,
    OrchestratorStatusEvent,
    OrchestratorCompletedEvent,
    OrchestratorFailedEvent
)
from transport_services.kafka.external_events.archive_events import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent
)
from transport_services.kafka.external_events.metadata_events import (
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent
)
from transport_services.transport_service_interface import TransportServiceInterface

logger = get_logger(__name__)


class KafkaTransportService(TransportServiceInterface):
    """
    Kafka transport service - handles ALL Kafka communication.

    Responsibilities:
    - Consume Kafka messages from all topics
    - Deserialize events
    - Delegate to OrchestratorService
    - Execute instructions from orchestrator
    - Publish events via EventPublisher

    What it DOES NOT do:
    - NO business logic
    - NO workflow decisions
    - NO state management
    - ONLY Kafka operations
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

        # Kafka components  # These will be created in start()
        self.consumer: KafkaConsumer | None = None
        self.producer: KafkaProducer | None = None
        self.event_publisher: EventPublisher | None = None
        self.event_handlers: dict[str, Callable] = {}

        # Initialize callback service
        self.callback_service = CallbackService()

        # Initialize producer and event publisher
        self._setup_producer()

    @staticmethod
    def _safe_json_deserializer(message: bytes | None) -> dict[str, Any] | None:
        """Decode bytes to JSON with resilience to malformed payloads."""
        if message is None:
            return None

        try:
            json_string = message.decode("utf-8", errors="ignore")
        except Exception:
            logger.warning("⚠️ Failed to decode Kafka message bytes; skipping")
            return None

        # Try to parse JSON
        try:
            return json.loads(json_string)
        except Exception:
            # Try to extract JSON substring
            start = json_string.find("{")
            end = json_string.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = json_string[start : end + 1]
                try:
                    return json.loads(candidate)
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse JSON: {e}")
                    return None

            logger.warning(f"⚠️ Received non-JSON message; skipping. Snippet: {json_string[:200]}")
            return None

    def _setup_producer(self):
        """Initialize Kafka producer and event publisher."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks=1,
                retries=3,
                max_in_flight_requests_per_connection=1,
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=30000,
            )

            # Initialize event publisher with topics as dict
            topics_dict = self.topics.model_dump()
            self.event_publisher = EventPublisher(self.producer, topics_dict)

            logger.info("✅ Kafka producer and event publisher initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka producer: {e}")
            raise

    def _setup_consumer(self):
        """Initialize Kafka consumer for all registered topics."""
        try:
            topics_to_consume = list(self.event_handlers.keys())
            if not topics_to_consume:
                logger.warning("⚠️ No topics registered for consumption")
                return

            self.consumer = KafkaConsumer(
                *topics_to_consume,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=self.kafka_config.consumer.group_id,
                value_deserializer=self._safe_json_deserializer,
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset=self.kafka_config.consumer.auto_offset_reset,
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=30000,
            )

            logger.info(f"✅ Kafka consumer initialized for topics: {topics_to_consume}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka consumer: {e}")
            raise

    def register_handler(self, topic: str, handler: Callable) -> None:
        """Register a message handler for a specific topic (implements interface)."""
        self.event_handlers[topic] = handler
        logger.info(f"✅ Registered handler for topic: {topic}")

    def _register_event_handlers(self):
        """Register event handlers for all topics."""
        # Orchestrator request handler
        self.register_handler(self.topics.orchestrator_requests, self._handle_orchestrator_request)

        # Archive generator response handlers (use adapter to get topics)
        archive_response_topics = self.adapter.get_response_destinations("archive_generator")
        self.register_handler(archive_response_topics["success"], self._handle_archive_completed)
        self.register_handler(archive_response_topics["failure"], self._handle_archive_failed)

        # Metadata extractor response handlers (use adapter to get topics)
        metadata_response_topics = self.adapter.get_response_destinations("metadata_extractor")
        self.register_handler(metadata_response_topics["success"], self._handle_metadata_completed)
        self.register_handler(metadata_response_topics["failure"], self._handle_metadata_failed)

        logger.info(f"✅ Registered {len(self.event_handlers)} event handlers")

    async def start(self):
        """Start the Kafka transport service."""
        try:
            logger.info("🚀 Starting Kafka transport service")

            # Register event handlers
            self._register_event_handlers()

            # Setup consumer
            self._setup_consumer()

            if not self.consumer:
                raise ValueError("Failed to setup Kafka consumer")

            self.running = True
            
            # Start consuming messages
            await self._start_consuming()

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka transport service: {e}")
            await self.stop()
            raise

    async def _start_consuming(self):
        """Start consuming messages from Kafka."""
        logger.info("📡 Starting to consume Kafka messages")

        while self.running:
            try:
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=1000)

                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue

                # Process all messages
                for _topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            await self._process_kafka_message(message)
                        except Exception as e:
                            logger.error(f"❌ Error processing message: {e}", exc_info=True)

                await asyncio.sleep(0.1)

            except Exception as e:
                if self.running:
                    logger.error(f"❌ Kafka polling error: {e}")
                    await asyncio.sleep(1)

    async def _process_kafka_message(self, message):
        """Process a single Kafka message."""
        try:
            topic = message.topic
            request_id = message.key or "unknown"
            message_data = message.value

            if message_data is None:
                logger.warning("⚠️ Received empty message; skipping")
                return

            logger.info(f"📥 Message received from {topic}: {request_id}")

            # Get handler for topic
            handler = self.event_handlers.get(topic)
            if not handler:
                logger.warning(f"⚠️ No handler for topic: {topic}")
                return

            # Call handler
            await handler(message, message_data)

        except Exception as e:
            logger.error(f"❌ Failed to process message: {e}", exc_info=True)

    # === EVENT HANDLERS (delegate to orchestrator) ===

    async def _handle_orchestrator_request(self, message, message_data: dict[str, Any]):
        """Handle orchestrator.requests event."""
        try:
            # 1. Deserialize event
            event = OrchestratorRequestEvent(**message_data)
            logger.info(f"🚀 Orchestrator request: {event.request_id} for {event.url}")

            # 2. Delegate to orchestrator - get instruction
            instruction = self.orchestrator.start_workflow(
                request_id=event.request_id,
                url=event.url,
                workflow_name=event.workflow_name,
                callback_url=event.callback_url,
                metadata=event.metadata
            )

            # 3. Execute instruction
            await self._execute_step_instruction(instruction)

        except Exception as e:
            logger.error(f"❌ Failed to handle orchestrator request: {e}", exc_info=True)

    async def _handle_archive_completed(self, message, message_data: dict[str, Any]):
        """Handle archive.completed event."""
        try:
            # 1. Deserialize event
            event = ArchiveCompletedEvent(**message_data)
            logger.info(f"✅ Archive completed: {event.request_id}")

            # 2. Delegate to orchestrator - get transition
            transition = self.orchestrator.step_completed(
                request_id=event.request_id,
                step_name="archive_generation",
                result_data={
                    "archive_path": event.archive_path,
                    "artifacts_created": event.artifacts_created,
                    "processing_time_seconds": event.processing_time_seconds,
                    "snapshot_id": event.snapshot_id  # Pass snapshot_id for metadata extraction
                }
            )

            # 3. Execute transition
            await self._execute_transition(transition)

        except Exception as e:
            logger.error(f"❌ Failed to handle archive completed: {e}", exc_info=True)

    async def _handle_archive_failed(self, message, message_data: dict[str, Any]):
        """Handle archive.failed event."""
        try:
            # 1. Deserialize event
            event = ArchiveFailedEvent(**message_data)
            logger.error(f"❌ Archive failed: {event.request_id}: {event.error_message}")

            # 2. Delegate to orchestrator - get transition
            transition = self.orchestrator.step_failed(
                request_id=event.request_id,
                step_name="archive_generation",
                error_message=event.error_message
            )

            # 3. Execute transition
            await self._execute_transition(transition)

        except Exception as e:
            logger.error(f"❌ Failed to handle archive failure: {e}", exc_info=True)

    async def _handle_metadata_completed(self, message, message_data: dict[str, Any]):
        """Handle metadata.completed event."""
        try:
            # 1. Deserialize event
            event = MetadataExtractionCompletedEvent(**message_data)
            logger.info(f"✅ Metadata extraction completed: {event.request_id}")

            # 2. Delegate to orchestrator - get transition
            transition = self.orchestrator.step_completed(
                request_id=event.request_id,
                step_name="metadata_extraction",
                result_data={
                    "extracted_metadata": event.extracted_metadata,
                    "domain_used": event.domain_used,
                    "mappers_used": event.mappers_used,
                    "processing_time_seconds": event.processing_time_seconds
                }
            )

            # 3. Execute transition
            await self._execute_transition(transition)

        except Exception as e:
            logger.error(f"❌ Failed to handle metadata completed: {e}", exc_info=True)

    async def _handle_metadata_failed(self, message, message_data: dict[str, Any]):
        """Handle metadata.failed event."""
        try:
            # 1. Deserialize event
            event = MetadataExtractionFailedEvent(**message_data)
            logger.error(f"❌ Metadata extraction failed: {event.request_id}: {event.error_message}")

            # 2. Delegate to orchestrator - get transition
            transition = self.orchestrator.step_failed(
                request_id=event.request_id,
                step_name="metadata_extraction",
                error_message=event.error_message
            )

            # 3. Execute transition
            await self._execute_transition(transition)

        except Exception as e:
            logger.error(f"❌ Failed to handle metadata failure: {e}", exc_info=True)

    # === INSTRUCTION EXECUTION ===

    async def _execute_step_instruction(self, instruction: StepInstruction):
        """Execute a step instruction by creating and publishing the appropriate event."""
        try:
            logger.info(f"📤 Executing step: {instruction.step_config.name}")

            # 1. Use adapter to translate instruction to Kafka operation
            kafka_operation = self.adapter.translate_instruction(instruction)

            # 2. Get event model class from registry
            event_model_class = get_event_model(kafka_operation["event_model"])

            # 3. Create event instance
            event = self._create_step_event(instruction, event_model_class)

            # 4. Publish event
            success = self.event_publisher.publish_event(
                topic=kafka_operation["topic"],
                key=instruction.request_id,
                event=event
            )

            if success:
                logger.info(
                    f"✅ Published {kafka_operation['event_model']} to {kafka_operation['topic']}"
                )
                # 5. Publish status update
                await self._publish_status_update(
                    request_id=instruction.request_id,
                    url=instruction.url,
                    workflow_name=instruction.workflow_instance.workflow_name,
                    step_name=instruction.step_config.name,
                    status="in_progress"
                )
            else:
                logger.error(
                    f"❌ Failed to publish {kafka_operation['event_model']}"
                )

        except Exception as e:
            logger.error(f"❌ Failed to execute step instruction: {e}", exc_info=True)
            raise

    async def _execute_transition(self, transition: WorkflowTransition):
        """Execute a workflow transition."""
        try:
            if transition.action == "execute_step":
                # Execute next step
                await self._execute_step_instruction(transition.step_instruction)

            elif transition.action == "workflow_complete":
                # Publish workflow completion
                await self._publish_workflow_completed(transition)

            elif transition.action == "workflow_failed":
                # Publish workflow failure
                await self._publish_workflow_failed(transition)

            else:
                logger.error(f"❌ Unknown transition action: {transition.action}")

        except Exception as e:
            logger.error(f"❌ Failed to execute transition: {e}", exc_info=True)

    # === EVENT CREATION ===

    def _create_step_event(
        self,
        instruction: StepInstruction,
        event_class: Type[BaseModel]
    ) -> BaseModel:
        """Create event instance from step instruction."""
        # Base fields all events have
        event_data = {
            "request_id": instruction.request_id,
            "url": instruction.url,
        }

        # Add fields from instruction.input_data
        if instruction.input_data:
            event_data.update(instruction.input_data)

        # Add metadata if present
        if instruction.metadata:
            event_data["metadata"] = instruction.metadata

        # Create event instance
        try:
            return event_class(**event_data)
        except Exception as e:
            logger.error(f"❌ Failed to create {event_class.__name__}: {e}")
            # Try with minimal fields
            return event_class(
                request_id=instruction.request_id,
                url=instruction.url
            )

    # === WORKFLOW COMPLETION/FAILURE PUBLISHING ===

    async def _publish_workflow_completed(self, transition: WorkflowTransition):
        """Publish workflow completion event."""
        try:
            workflow_instance = transition.workflow_instance

            event = OrchestratorCompletedEvent(
                request_id=workflow_instance.request_id,
                url=workflow_instance.url,
                workflow_name=workflow_instance.workflow_name,
                completed_steps=list(workflow_instance.completed_steps),
                processing_time_seconds=workflow_instance.processing_time_seconds or 0.0,
                step_results=workflow_instance.step_results
            )

            success = self.event_publisher.publish_event(
                topic=self.topics.orchestrator_completed,
                key=workflow_instance.request_id,
                event=event
            )

            if success:
                logger.info(f"✅ Workflow completed: {workflow_instance.request_id}")
                
                # 5. Send callback if configured
                if workflow_instance.callback_url:
                    await self.callback_service.send_callback(
                        workflow_instance.callback_url,
                        event.model_dump(),
                        workflow_instance.request_id
                    )
            else:
                logger.error(f"❌ Failed to publish completion event")

        except Exception as e:
            logger.error(f"❌ Failed to publish workflow completion: {e}", exc_info=True)

    async def _publish_workflow_failed(self, transition: WorkflowTransition):
        """Publish workflow failure event."""
        try:
            workflow_instance = transition.workflow_instance

            event = OrchestratorFailedEvent(
                request_id=workflow_instance.request_id,
                url=workflow_instance.url,
                workflow_name=workflow_instance.workflow_name,
                failed_step=transition.failed_step,
                error_message=transition.error_message,
                completed_steps=list(workflow_instance.completed_steps)
            )

            success = self.event_publisher.publish_event(
                topic=self.topics.orchestrator_failed,
                key=workflow_instance.request_id,
                event=event
            )

            if success:
                logger.error(
                    f"❌ Workflow failed: {workflow_instance.request_id} "
                    f"at step {transition.failed_step}"
                )
                
                # 5. Send callback if configured
                if workflow_instance.callback_url:
                    await self.callback_service.send_callback(
                        workflow_instance.callback_url,
                        event.model_dump(),
                        workflow_instance.request_id
                    )
            else:
                logger.error(f"❌ Failed to publish failure event")

        except Exception as e:
            logger.error(f"❌ Failed to publish workflow failure: {e}", exc_info=True)

    async def _publish_status_update(
        self,
        request_id: str,
        url: str,
        workflow_name: str,
        step_name: str,
        status: str,
        message: Optional[str] = None
    ):
        """Publish a status update event to Kafka."""
        try:
            event = OrchestratorStatusEvent(
                request_id=request_id,
                url=url,
                workflow_name=workflow_name,
                current_step=step_name,
                status=status,
                message=message
            )

            success = self.event_publisher.publish_event(
                topic=self.topics.orchestrator_status,
                key=request_id,
                event=event
            )

            if success:
                logger.info(f"📊 Published status update: {request_id} - {step_name} [{status}]")
                
                # 6. Send callback if configured
                # Retrieve workflow instance to get callback_url
                workflow_instance = self.orchestrator.get_workflow_state(request_id)
                if workflow_instance and workflow_instance.callback_url:
                    await self.callback_service.send_callback(
                        workflow_instance.callback_url,
                        event.model_dump(),
                        request_id
                    )
        except Exception as e:
            logger.error(f"❌ Failed to publish status update: {e}")

    # === UTILITY METHODS ===

    async def stop(self):
        """Stop the Kafka transport service and cleanup resources."""
        logger.info("🛑 Stopping Kafka transport service")
        self.running = False

        try:
            if self.consumer:
                self.consumer.close()
                logger.info("✅ Kafka consumer closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing consumer: {e}")

        try:
            if self.producer:
                self.producer.close()
                logger.info("✅ Kafka producer closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing producer: {e}")

        logger.info("✅ Kafka transport service stopped")

    async def health_check(self) -> dict[str, Any]:
        """Check health of Kafka transport service."""
        try:
            health_status = {
                "service": "kafka_transport",
                "running": self.running,
                "producer_ready": self.producer is not None,
                "consumer_ready": self.consumer is not None,
                "event_publisher_ready": self.event_publisher is not None,
                "registered_topics": list(self.event_handlers.keys()),
            }

            return {
                "healthy": self.producer is not None and self.event_publisher is not None,
                "running": self.running,
                "details": health_status,
            }

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def send_response(
        self, destination: str, message: dict[str, Any], **kwargs
    ) -> bool:
        """Send a response message to a Kafka topic (for backwards compatibility)."""
        try:
            key = kwargs.get("key", None)
            return self.event_publisher.publish_dict(destination, key, message)
        except Exception as e:
            logger.error(f"❌ Failed to send response: {e}")
            return False

    def get_transport_info(self) -> dict[str, Any]:
        """Get transport service information."""
        return {
            "transport_type": "KafkaTransportService",
            "version": "2.0-instruction-based",
            "kafka_config": {
                "bootstrap_servers": self.kafka_config.bootstrap_servers,
                "consumer_group": self.kafka_config.consumer.group_id,
            },
            "status": {
                "running": self.running,
                "producer_ready": self.producer is not None,
                "consumer_ready": self.consumer is not None,
                "event_publisher_ready": self.event_publisher is not None,
                "registered_handlers": len(self.event_handlers),
            },
            "architecture": {
                "pattern": "instruction-based",
                "orchestrator_dependency": True,
                "business_logic": "delegated_to_orchestrator",
            },
        }
