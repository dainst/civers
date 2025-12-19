"""Abstract interface for transport adapters.

This interface defines the contract that any transport mechanism
(Kafka, REST, Redis, etc.) must implement to translate transport-agnostic
workflow instructions into transport-specific operations.

Example:
    class KafkaTransportAdapter(TransportAdapter):
        def get_request_destination(self, component: str) -> str:
            return self.mappings[component]["request_topic"]

        def translate_instruction(self, instruction) -> Dict[str, Any]:
            return {
                "topic": self.get_request_destination(instruction.component),
                "event_model": self.get_message_type(instruction.component, "request"),
                "data": instruction.input_data
            }
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class TransportAdapter(ABC):
    """
    Abstract interface for transport adapters.

    Adapters translate transport-agnostic StepInstructions into
    transport-specific operations (topics, endpoints, queues, etc.).

    Each transport implementation (Kafka, REST, Redis) provides
    a concrete adapter implementing this interface.

    This enables:
    - Workflows to be transport-agnostic
    - Easy addition of new transports
    - Configuration-driven routing
    - Better testing (mock adapters)
    """

    @abstractmethod
    def get_request_destination(self, component: str) -> str:
        """
        Get transport-specific destination for component requests.

        Args:
            component: Component identifier (e.g., "archive_generator")

        Returns:
            Transport-specific destination:
            - Kafka: topic name (e.g., "archive.requests")
            - REST: endpoint (e.g., "/api/v1/archive/generate")
            - Redis: queue name (e.g., "archive:requests")

        Raises:
            ValueError: If component has no configured mapping

        Example:
            >>> adapter.get_request_destination("archive_generator")
            'archive.requests'
        """
        pass

    @abstractmethod
    def get_response_destinations(self, component: str) -> Dict[str, str]:
        """
        Get transport-specific destinations for component responses.

        Args:
            component: Component identifier

        Returns:
            Dictionary mapping outcome to destination:
            {
                "success": "archive.completed",  # Kafka topic
                "failure": "archive.failed"
            }

        Raises:
            ValueError: If component has no configured mapping

        Example:
            >>> adapter.get_response_destinations("archive_generator")
            {'success': 'archive.completed', 'failure': 'archive.failed'}
        """
        pass

    @abstractmethod
    def translate_instruction(self, instruction: Any) -> Dict[str, Any]:
        """
        Translate StepInstruction into transport-specific operation.

        Args:
            instruction: Transport-agnostic step instruction

        Returns:
            Transport-specific operation dictionary containing:
            - destination: Where to send (topic/endpoint/queue)
            - message_type: Type of message (event class/schema)
            - data: Payload to send
            - metadata: Additional transport metadata

        Example (Kafka):
            >>> instruction = StepInstruction(component="archive_generator", ...)
            >>> adapter.translate_instruction(instruction)
            {
                "topic": "archive.requests",
                "event_model": "ArchiveRequestEvent",
                "event_data": {"url": "...", "request_id": "..."},
                "key": "req-123"
            }

        Example (REST):
            >>> adapter.translate_instruction(instruction)
            {
                "endpoint": "/api/v1/archive/generate",
                "method": "POST",
                "payload": {"url": "...", "request_id": "..."},
                "headers": {"Content-Type": "application/json"}
            }
        """
        pass

    @abstractmethod
    def get_message_type(self, component: str, outcome: str) -> str:
        """
        Get message type (event model, schema) for component and outcome.

        Args:
            component: Component identifier
            outcome: "request", "success", or "failure"

        Returns:
            Message type identifier:
            - Kafka: Event model class name (e.g., "ArchiveRequestEvent")
            - REST: Schema name (e.g., "ArchiveRequestSchema")
            - Redis: Message type string

        Raises:
            ValueError: If component or outcome not configured

        Example:
            >>> adapter.get_message_type("archive_generator", "request")
            'ArchiveRequestEvent'

            >>> adapter.get_message_type("archive_generator", "success")
            'ArchiveCompletedEvent'
        """
        pass
