"""Kafka transport adapter implementation.

This adapter translates transport-agnostic component identifiers into
Kafka-specific topics and event model names.

Task 12 Update:
Component mappings are now loaded from kafka.yaml configuration
(config.transport.kafka.component_mappings), providing proper separation
between transport-agnostic workflows and Kafka-specific routing.

Example:
    from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
    from configs.loaders import YamlFileConfigLoader

    config = YamlFileConfigLoader().load()
    adapter = KafkaTransportAdapter(config.transport.kafka)

    # Get destination for component
    topic = adapter.get_request_destination("archive_generator")
    # Returns: "archive.requests"

    # Translate instruction
    instruction = StepInstruction(component="archive_generator", ...)
    operation = adapter.translate_instruction(instruction)
    # Returns: {"topic": "archive.requests", "event_model": "ArchiveRequestEvent", ...}
"""

from typing import Any

from transport_services.adapters.transport_adapter_interface import TransportAdapter


class KafkaTransportAdapter(TransportAdapter):
    """
    Kafka-specific transport adapter.

    Translates transport-agnostic component identifiers into Kafka topics
    and event model names by reading component mappings from Kafka configuration.

    Component mappings are defined in configs/data/defaults/kafka.yaml under
    the component_mappings section.

    Attributes:
        component_mappings: Dict mapping component IDs to Kafka topics/events
    """

    def __init__(self, kafka_config: Any):
        """
        Initialize Kafka adapter with Kafka configuration.

        Loads component mappings from kafka_config.component_mappings.

        Args:
            kafka_config: KafkaConfig object with component_mappings attribute

        Example:
            >>> from configs.loaders import YamlFileConfigLoader
            >>> config = YamlFileConfigLoader().load()
            >>> adapter = KafkaTransportAdapter(config.transport.kafka)
            >>> assert "archive_generator" in adapter.component_mappings
        """
        self.component_mappings: dict[str, dict[str, Any]] = {}
        self._load_component_mappings(kafka_config)

    def _load_component_mappings(self, kafka_config: Any):
        """
        Load component mappings from Kafka configuration.

        Converts KafkaComponentMapping Pydantic models into the internal
        dictionary format used by the adapter.

        Args:
            kafka_config: KafkaConfig object with component_mappings attribute
        """
        if not hasattr(kafka_config, 'component_mappings'):
            return

        # Convert Pydantic models to internal dict format
        for component_id, mapping_model in kafka_config.component_mappings.items():
            self.component_mappings[component_id] = {
                "request_topic": mapping_model.request_topic,
                "response_topics": mapping_model.response_topics,
                "event_models": mapping_model.event_models
            }

    def get_request_destination(self, component: str) -> str:
        """
        Get Kafka topic for component requests.

        Args:
            component: Component identifier (e.g., "archive_generator")

        Returns:
            Kafka topic name (e.g., "archive.requests")

        Raises:
            ValueError: If component has no configured mapping

        Example:
            >>> adapter.get_request_destination("archive_generator")
            'archive.requests'
        """
        if component not in self.component_mappings:
            raise ValueError(
                f"No mapping found for component '{component}'. "
                f"Available components: {list(self.component_mappings.keys())}"
            )

        topic = self.component_mappings[component]["request_topic"]
        if not topic:
            raise ValueError(
                f"Component '{component}' has no request_topic configured"
            )

        return topic

    def get_response_destinations(self, component: str) -> dict[str, str]:
        """
        Get Kafka topics for component responses.

        Args:
            component: Component identifier

        Returns:
            Dictionary with success/failure topics:
            {
                "success": "archive.completed",
                "failure": "archive.failed"
            }

        Raises:
            ValueError: If component has no configured mapping

        Example:
            >>> adapter.get_response_destinations("archive_generator")
            {'success': 'archive.completed', 'failure': 'archive.failed'}
        """
        if component not in self.component_mappings:
            raise ValueError(
                f"No mapping found for component '{component}'. "
                f"Available components: {list(self.component_mappings.keys())}"
            )

        return self.component_mappings[component]["response_topics"]

    def get_message_type(self, component: str, outcome: str) -> str:
        """
        Get event model name for component and outcome.

        Args:
            component: Component identifier
            outcome: "request", "success", or "failure"

        Returns:
            Event model class name (e.g., "ArchiveRequestEvent")

        Raises:
            ValueError: If component not configured or invalid outcome

        Example:
            >>> adapter.get_message_type("archive_generator", "request")
            'ArchiveRequestEvent'

            >>> adapter.get_message_type("archive_generator", "success")
            'ArchiveCompletedEvent'
        """
        if component not in self.component_mappings:
            raise ValueError(
                f"No mapping found for component '{component}'. "
                f"Available components: {list(self.component_mappings.keys())}"
            )

        if outcome not in ["request", "success", "failure"]:
            raise ValueError(
                f"Invalid outcome '{outcome}'. "
                f"Must be 'request', 'success', or 'failure'"
            )

        event_model = self.component_mappings[component]["event_models"].get(outcome)
        if not event_model:
            raise ValueError(
                f"Component '{component}' has no event model configured for outcome '{outcome}'"
            )

        return event_model

    def translate_instruction(self, instruction: Any) -> dict[str, Any]:
        """
        Translate transport-agnostic instruction to Kafka operation.

        Args:
            instruction: StepInstruction with component identifier

        Returns:
            Kafka operation dictionary:
            {
                "topic": "archive.requests",
                "event_model": "ArchiveRequestEvent",
                "event_data": {"url": "...", "request_id": "..."},
                "key": "req-123",
                "metadata": {...}
            }

        Raises:
            ValueError: If component has no configured mapping

        Example:
            >>> instruction = StepInstruction(
            ...     component="archive_generator",
            ...     request_id="req-123",
            ...     input_data={"url": "https://example.com"}
            ... )
            >>> operation = adapter.translate_instruction(instruction)
            >>> assert operation["topic"] == "archive.requests"
            >>> assert operation["event_model"] == "ArchiveRequestEvent"
        """
        component = instruction.component

        # Get Kafka-specific destination and event model
        topic = self.get_request_destination(component)
        event_model = self.get_message_type(component, "request")

        # Build event data
        event_data = {
            "request_id": instruction.request_id,
            **instruction.input_data
        }

        # Build Kafka operation
        operation = {
            "topic": topic,
            "event_model": event_model,
            "event_data": event_data,
            "key": instruction.request_id  # Use request_id as Kafka key for partitioning
        }

        # Include metadata if present
        if hasattr(instruction, 'metadata') and instruction.metadata:
            operation["metadata"] = instruction.metadata

        return operation
