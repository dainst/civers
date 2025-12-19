"""Unit tests for TransportServiceInterface."""

import pytest
from abc import ABC


class TestTransportServiceInterface:
    """Tests for TransportServiceInterface abstract base class."""

    def test_transport_interface_is_abstract(self):
        """Test that TransportServiceInterface is an abstract base class."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert issubclass(TransportServiceInterface, ABC)

    def test_cannot_instantiate_interface_directly(self):
        """Test that TransportServiceInterface cannot be instantiated directly."""
        from transport_services.transport_service_interface import TransportServiceInterface

        with pytest.raises(TypeError) as exc_info:
            TransportServiceInterface()

        assert "abstract" in str(exc_info.value).lower()

    def test_interface_has_start_method(self):
        """Test that interface defines start method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "start")
        assert callable(getattr(TransportServiceInterface, "start"))

    def test_interface_has_stop_method(self):
        """Test that interface defines stop method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "stop")
        assert callable(getattr(TransportServiceInterface, "stop"))

    def test_interface_has_register_handler_method(self):
        """Test that interface defines register_handler method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "register_handler")
        assert callable(getattr(TransportServiceInterface, "register_handler"))

    def test_interface_has_health_check_method(self):
        """Test that interface defines health_check method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "health_check")
        assert callable(getattr(TransportServiceInterface, "health_check"))

    def test_interface_has_send_response_method(self):
        """Test that interface defines send_response method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "send_response")
        assert callable(getattr(TransportServiceInterface, "send_response"))

    def test_interface_has_get_transport_info_method(self):
        """Test that interface defines get_transport_info method."""
        from transport_services.transport_service_interface import TransportServiceInterface

        assert hasattr(TransportServiceInterface, "get_transport_info")
        assert callable(getattr(TransportServiceInterface, "get_transport_info"))

    def test_concrete_class_must_implement_all_methods(self):
        """Test that concrete subclass must implement all abstract methods."""
        from transport_services.transport_service_interface import TransportServiceInterface

        # Create incomplete implementation
        class IncompleteTransport(TransportServiceInterface):
            async def start(self):
                pass

        # Should not be able to instantiate incomplete implementation
        with pytest.raises(TypeError) as exc_info:
            IncompleteTransport()

        assert "abstract" in str(exc_info.value).lower()

    def test_complete_implementation_can_be_instantiated(self):
        """Test that complete implementation can be instantiated."""
        from transport_services.transport_service_interface import TransportServiceInterface

        # Create complete implementation
        class CompleteTransport(TransportServiceInterface):
            async def start(self):
                pass

            async def stop(self):
                pass

            def register_handler(self, topic, handler):
                pass

            async def health_check(self):
                return {"status": "healthy"}

            async def send_response(self, destination, message, **kwargs):
                return True

            def get_transport_info(self):
                return {"type": "test"}

        # Should be able to instantiate complete implementation
        transport = CompleteTransport()
        assert transport is not None
        assert isinstance(transport, TransportServiceInterface)

    def test_concrete_implementation_has_correct_signatures(self):
        """Test that concrete implementation methods work correctly."""
        from transport_services.transport_service_interface import TransportServiceInterface
        import asyncio

        class TestTransport(TransportServiceInterface):
            def __init__(self):
                self.started = False
                self.stopped = False
                self.handlers = {}

            async def start(self):
                self.started = True

            async def stop(self):
                self.stopped = True

            def register_handler(self, topic, handler):
                self.handlers[topic] = handler

            async def health_check(self):
                return {"status": "healthy", "started": self.started}

            async def send_response(self, destination, message, **kwargs):
                return True

            def get_transport_info(self):
                return {"type": "test", "handlers": len(self.handlers)}

        transport = TestTransport()

        # Test synchronous methods
        transport.register_handler("test_topic", lambda x: x)
        info = transport.get_transport_info()
        assert info["type"] == "test"
        assert info["handlers"] == 1

        # Test async methods
        async def run_async_tests():
            await transport.start()
            assert transport.started is True

            health = await transport.health_check()
            assert health["status"] == "healthy"
            assert health["started"] is True

            result = await transport.send_response("dest", {"data": "test"})
            assert result is True

            await transport.stop()
            assert transport.stopped is True

        asyncio.run(run_async_tests())
