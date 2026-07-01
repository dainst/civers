"""Pytest configuration and fixtures for unit tests."""

# Import fixtures to make them available to all unit tests
from tests.fixtures.adapter_fixtures import kafka_component_mappings, mock_transport_adapter

__all__ = [
    "kafka_component_mappings",
    "mock_transport_adapter"
]
