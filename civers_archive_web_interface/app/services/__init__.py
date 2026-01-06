"""
Services package for Civers Archive Web Interface.

This package provides service classes for external integrations
such as Kafka, domain management, etc.
"""

from .kafka_producer import KafkaProducerService

__all__ = [
    "KafkaProducerService",
]
