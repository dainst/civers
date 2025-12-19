"""Transport adapter interfaces and implementations.

Available adapters:
- TransportAdapter: Abstract base interface
- KafkaTransportAdapter: Kafka-specific implementation
"""

from transport_services.adapters.transport_adapter_interface import TransportAdapter
from transport_services.adapters.kafka_adapter import KafkaTransportAdapter

__all__ = ["TransportAdapter", "KafkaTransportAdapter"]
