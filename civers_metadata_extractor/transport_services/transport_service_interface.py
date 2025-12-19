# transport_services/transport_service_interface.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional


class TransportServiceInterface(ABC):
    """
    Interface for transport services that handle archive requests.
    
    Transport services are responsible for:
    1. Receiving archive requests from external sources (Kafka, HTTP, etc.)
    2. Delegating processing to ArchiveService
    3. Sending responses/status updates back to the requester
    4. Managing transport-specific connections and configurations
    """
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the transport service.
        
        This should initialize connections, start listening for requests,
        and begin processing messages.
        
        Raises:
            Exception: If the service fails to start
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the transport service gracefully.
        
        This should:
        1. Stop accepting new requests
        2. Complete processing of current requests
        3. Close connections and cleanup resources
        """
        pass
    
    @abstractmethod
    def register_handler(self, topic: str, handler: Callable) -> None:
        """
        Register a message handler for a specific topic/endpoint.
        
        Args:
            topic: The topic/endpoint identifier
            handler: Callable to handle messages from this topic
        """
        pass
    
    
    @abstractmethod
    async def send_response(self, destination: str, message: Dict[str, Any], **kwargs) -> bool:
        """
        Send a response message to a destination.
        
        Args:
            destination: Where to send the message (topic, endpoint, etc.)
            message: The message to send
            **kwargs: Transport-specific options
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_transport_info(self) -> Dict[str, Any]:
        """
        Get information about the transport service configuration.
        
        Returns:
            Dict containing transport service information and capabilities
        """
        pass
