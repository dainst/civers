"""Tests for transport adapter interface.

Following TDD: These tests define the abstract adapter interface contract
that all concrete adapters (Kafka, REST, Redis) must implement.
"""

import pytest
from abc import ABC


class TestTransportAdapterInterface:
    """Test the abstract adapter interface definition."""

    def test_interface_is_abstract(self):
        """Test TransportAdapter cannot be instantiated directly."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            TransportAdapter()

    def test_interface_is_abc_subclass(self):
        """Test TransportAdapter is an ABC."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        assert issubclass(TransportAdapter, ABC)

    def test_interface_defines_get_request_destination(self):
        """Test interface defines get_request_destination method."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        assert hasattr(TransportAdapter, "get_request_destination")
        assert callable(getattr(TransportAdapter, "get_request_destination"))

    def test_interface_defines_get_response_destinations(self):
        """Test interface defines get_response_destinations method."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        assert hasattr(TransportAdapter, "get_response_destinations")
        assert callable(getattr(TransportAdapter, "get_response_destinations"))

    def test_interface_defines_translate_instruction(self):
        """Test interface defines translate_instruction method."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        assert hasattr(TransportAdapter, "translate_instruction")
        assert callable(getattr(TransportAdapter, "translate_instruction"))

    def test_interface_defines_get_message_type(self):
        """Test interface defines get_message_type method."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        assert hasattr(TransportAdapter, "get_message_type")
        assert callable(getattr(TransportAdapter, "get_message_type"))

    def test_concrete_adapter_must_implement_all_methods(self):
        """Test concrete adapter without implementations cannot be instantiated."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        class IncompleteAdapter(TransportAdapter):
            # Missing all abstract methods
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteAdapter()

    def test_concrete_adapter_with_partial_implementation_fails(self):
        """Test concrete adapter with only some methods cannot be instantiated."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter

        class PartialAdapter(TransportAdapter):
            def get_request_destination(self, component: str) -> str:
                return "test"
            # Missing other abstract methods

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialAdapter()

    def test_concrete_adapter_with_full_implementation_succeeds(self):
        """Test concrete adapter with all methods can be instantiated."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        from typing import Dict, Any

        class CompleteAdapter(TransportAdapter):
            def get_request_destination(self, component: str) -> str:
                return "test.destination"

            def get_response_destinations(self, component: str) -> Dict[str, str]:
                return {"success": "test.success", "failure": "test.failure"}

            def translate_instruction(self, instruction) -> Dict[str, Any]:
                return {"destination": "test"}

            def get_message_type(self, component: str, outcome: str) -> str:
                return "TestMessage"

        # Should not raise
        adapter = CompleteAdapter()
        assert adapter is not None


class TestTransportAdapterMethodSignatures:
    """Test adapter interface method signatures."""

    def test_get_request_destination_signature(self):
        """Test get_request_destination has correct signature."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        import inspect

        method = TransportAdapter.get_request_destination
        sig = inspect.signature(method)

        # Should have 'component' parameter
        assert 'component' in sig.parameters
        # Should return str
        assert sig.return_annotation == str

    def test_get_response_destinations_signature(self):
        """Test get_response_destinations has correct signature."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        import inspect
        from typing import Dict

        method = TransportAdapter.get_response_destinations
        sig = inspect.signature(method)

        # Should have 'component' parameter
        assert 'component' in sig.parameters
        # Return annotation should be Dict
        assert 'Dict' in str(sig.return_annotation)

    def test_translate_instruction_signature(self):
        """Test translate_instruction has correct signature."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        import inspect

        method = TransportAdapter.translate_instruction
        sig = inspect.signature(method)

        # Should have 'instruction' parameter
        assert 'instruction' in sig.parameters

    def test_get_message_type_signature(self):
        """Test get_message_type has correct signature."""
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        import inspect

        method = TransportAdapter.get_message_type
        sig = inspect.signature(method)

        # Should have 'component' and 'outcome' parameters
        assert 'component' in sig.parameters
        assert 'outcome' in sig.parameters
        # Should return str
        assert sig.return_annotation == str
