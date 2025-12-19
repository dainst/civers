"""Abstract interface for transport services in CiVers Orchestrator.

This interface defines the contract that any transport mechanism
(Kafka, HTTP, gRPC, etc.) must implement to be used by the orchestrator.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class TransportServiceInterface(ABC):
    """Abstract base class for transport services.

    Defines the interface that all transport implementations must follow,
    enabling pluggable transport mechanisms for the orchestrator.

    Transport implementations handle:
    - Starting and stopping the transport
    - Registering message handlers for topics/channels
    - Sending responses to destinations
    - Health monitoring
    - Providing transport configuration information
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the transport service.

        Initializes connections, creates consumers/producers,
        and begins listening for messages.

        This method should be called before any message handling begins.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport service gracefully.

        Closes connections, flushes pending messages,
        and performs cleanup operations.

        This method should be called during application shutdown.
        """
        pass

    @abstractmethod
    def register_handler(self, topic: str, handler: Callable) -> None:
        """Register a message handler for a specific topic/channel.

        Args:
            topic: The topic or channel name to listen on
            handler: Callable that processes messages from this topic.
                     Should accept the message as a parameter.

        The handler will be invoked whenever a message arrives on the topic.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the transport service.

        Returns:
            Dictionary containing health status information.
            Should include at minimum:
            - 'status': 'healthy' or 'unhealthy'
            - Additional diagnostic information as needed

        Example:
            {
                'status': 'healthy',
                'connected': True,
                'lag': 0
            }
        """
        pass

    @abstractmethod
    async def send_response(
        self, destination: str, message: Dict[str, Any], **kwargs
    ) -> bool:
        """Send a response message to a destination topic/channel.

        Args:
            destination: The topic or channel to send to
            message: The message payload as a dictionary
            **kwargs: Additional transport-specific parameters

        Returns:
            True if message was sent successfully, False otherwise

        Raises:
            TransportException: If sending fails critically
        """
        pass

    @abstractmethod
    def get_transport_info(self) -> Dict[str, Any]:
        """Get information about the transport configuration.

        Returns:
            Dictionary containing transport information such as:
            - Transport type (kafka, http, etc.)
            - Configuration details
            - Connection information

        Example:
            {
                'type': 'kafka',
                'bootstrap_servers': 'localhost:29092',
                'consumer_group': 'civers_orchestrator'
            }
        """
        pass
