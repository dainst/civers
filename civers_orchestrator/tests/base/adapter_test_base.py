"""Base test class for transport adapters.

Concrete adapter tests (Kafka, REST, Redis) inherit from this
to ensure they all implement required adapter interface.

Usage:
    class TestKafkaAdapter(AdapterTestBase):
        @pytest.fixture
        def adapter(self):
            config = load_config()
            return KafkaTransportAdapter(config)

        @pytest.fixture
        def component_mappings(self, kafka_component_mappings):
            return kafka_component_mappings
"""

from abc import ABC, abstractmethod

import pytest


class AdapterTestBase(ABC):
    """
    Base class for testing transport adapter implementations.

    Concrete adapter tests (Kafka, REST, Redis) inherit from this
    to ensure they all implement required adapter interface.

    Subclasses must implement:
    - adapter() fixture: Provides adapter instance to test
    - component_mappings() fixture: Provides component mappings for adapter
    """

    @pytest.fixture
    @abstractmethod
    def adapter(self):
        """
        Fixture providing adapter instance to test.

        Must be implemented by subclass.

        Returns:
            Transport adapter instance (e.g., KafkaTransportAdapter)

        Example:
            >>> @pytest.fixture
            ... def adapter(self):
            ...     config = load_config()
            ...     return KafkaTransportAdapter(config)
        """
        pass

    @pytest.fixture
    @abstractmethod
    def component_mappings(self):
        """
        Fixture providing component mappings for adapter.

        Must be implemented by subclass.

        Returns:
            Dict of component mappings

        Example:
            >>> @pytest.fixture
            ... def component_mappings(self, kafka_component_mappings):
            ...     return kafka_component_mappings
        """
        pass

    def test_get_request_destination(self, adapter, component_mappings):
        """Test adapter can resolve request destination for component."""
        component = list(component_mappings.keys())[0]
        destination = adapter.get_request_destination(component)

        assert destination is not None
        assert isinstance(destination, str)
        assert len(destination) > 0

    def test_get_response_destinations(self, adapter, component_mappings):
        """Test adapter can resolve response destinations."""
        component = list(component_mappings.keys())[0]
        destinations = adapter.get_response_destinations(component)

        assert "success" in destinations
        assert "failure" in destinations
        assert isinstance(destinations["success"], str)
        assert isinstance(destinations["failure"], str)

    def test_translate_instruction(self, adapter):
        """Test adapter can translate StepInstruction to transport operation."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction(
            component="archive_generator",
            input_data={"url": "https://example.com"}
        )

        operation = adapter.translate_instruction(instruction)

        # Generic assertions - all adapters should return these
        assert operation is not None
        assert isinstance(operation, dict)

        # Should have some identifier field
        has_id = ("request_id" in operation or
                  "id" in operation or
                  "key" in operation)
        assert has_id, "Operation should have an identifier field"

        # Should have data/payload field
        has_data = ("data" in operation or
                    "payload" in operation or
                    "event_data" in operation)
        assert has_data, "Operation should have a data field"

    def test_invalid_component_raises_error(self, adapter):
        """Test adapter raises error for unmapped component."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction(
            component="nonexistent_component_xyz"
        )

        with pytest.raises((ValueError, KeyError)):
            adapter.translate_instruction(instruction)

    def test_adapter_handles_multiple_components(self, adapter, component_mappings):
        """Test adapter can handle multiple different components."""
        if len(component_mappings) < 2:
            pytest.skip("Need at least 2 components to test")

        components = list(component_mappings.keys())[:2]

        dest1 = adapter.get_request_destination(components[0])
        dest2 = adapter.get_request_destination(components[1])

        # Different components should (usually) have different destinations
        # This is a weak assertion but generally holds
        assert isinstance(dest1, str)
        assert isinstance(dest2, str)
