"""
Comprehensive test suite for the main application orchestrator.

This test suite covers all aspects of the MetadataExtractionApp including:
- Application initialization and startup
- Configuration loading and validation
- Service initialization and health checks
- Signal handling and graceful shutdown  
- Error handling and failure scenarios
- Resource cleanup

NOTE: These tests use the new YamlFileConfigLoader-based configuration system
and verify application initialization, startup, and signal handling using
dependency injection and mocking.
"""

import sys
import types
import importlib
import signal
import os
import tempfile
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel, AppConfig
from main import MetadataExtractionApp


def _stub_aiokafka_modules():
    """Provide minimal aiokafka stubs so importing main doesn't require the real package."""
    if 'aiokafka' in sys.modules:
        return  # already stubbed or installed

    aiokafka_stub = types.ModuleType("aiokafka")

    class DummyProducer:  # noqa: D401 - simple stub
        """Stub AIOKafkaProducer"""
        pass

    class DummyConsumer:  # noqa: D401 - simple stub
        """Stub AIOKafkaConsumer"""
        pass

    aiokafka_stub.AIOKafkaProducer = DummyProducer
    aiokafka_stub.AIOKafkaConsumer = DummyConsumer

    errors_stub = types.ModuleType("aiokafka.errors")

    class KafkaError(Exception):
        pass

    errors_stub.KafkaError = KafkaError

    sys.modules['aiokafka'] = aiokafka_stub
    sys.modules['aiokafka.errors'] = errors_stub


@pytest.fixture(autouse=True)
def setup_aiokafka_stubs():
    """Automatically stub aiokafka for all tests."""
    _stub_aiokafka_modules()
    importlib.invalidate_caches()


def create_mock_config():
    """Create a mock ConfigDataModel with all required attributes for MetadataExtractionApp."""
    mock_config = MagicMock(spec=ConfigDataModel)
    mock_config.app = MagicMock(spec=AppConfig)
    mock_config.app.name = "test_app"
    mock_config.app.version = "1.0.0"
    mock_config.app.transport = MagicMock()
    mock_config.domains = []
    return mock_config




class TestMetadataExtractionAppInitialization:
    """Test cases for application initialization."""
    
    @pytest.mark.unit
    def test_app_initialization_with_default_loader(self):
        """Test that app initializes with default loader if none provided."""
        app = MetadataExtractionApp()
        
        assert app.config_loader is None
        assert app.config is None
        assert app.kafka_transport is None
        assert app.running is False

    @pytest.mark.unit
    def test_app_initialization_with_custom_loader(self):
        """Test that app initializes with a custom loader."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        app = MetadataExtractionApp(config_loader=mock_loader)
        
        assert app.config_loader == mock_loader
        assert app.config is None
        assert app.kafka_transport is None
        assert app.running is False

    @pytest.mark.unit
    async def test_initialize_success(self):
        """Test successful application initialization."""
        # Setup mocks
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService') as mock_metadata_service, \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_metadata_instance = AsyncMock()
            mock_metadata_service.return_value = mock_metadata_instance
            
            mock_kafka_instance = AsyncMock()
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            result = await app.initialize()
            
            assert result is True
            assert app.config == mock_config
            assert app.kafka_transport == mock_kafka_instance
            mock_loader.load.assert_called_once()
            mock_metadata_service.assert_called_once_with(mock_config)
            mock_kafka_service.assert_called_once_with(mock_config, mock_metadata_instance)

    @pytest.mark.unit
    async def test_initialize_failure_invalid_config(self):
        """Test initialization failure with invalid configuration."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.load.side_effect = Exception("Configuration validation failed")
        
        app = MetadataExtractionApp(config_loader=mock_loader)
        result = await app.initialize()
        
        assert result is False
        assert app.config is None
        assert app.kafka_transport is None

    @pytest.mark.unit
    async def test_initialize_failure_service_error(self):
        """Test initialization failure when service creation fails."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService') as mock_metadata_service:
            mock_metadata_service.side_effect = Exception("Service creation failed")
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            result = await app.initialize()
            
            assert result is False
            assert app.kafka_transport is None

    @pytest.mark.unit
    async def test_initialize_with_unhealthy_kafka(self):
        """Test initialization continues even with unhealthy Kafka service."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService') as mock_metadata_service, \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            # Setup mocks
            mock_metadata_instance = AsyncMock()
            mock_metadata_instance.config_data_model.get_supported_domains.return_value = ['test.domain.org']
            mock_metadata_service.return_value = mock_metadata_instance
            
            mock_kafka_instance = AsyncMock()
            # Note: health_check might not exist anymore or might be handled differently
            if hasattr(mock_kafka_instance, 'health_check'):
                mock_kafka_instance.health_check.return_value = {
                    'healthy': False,
                    'details': {'error': 'Connection failed'}
                }
            
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            result = await app.initialize()
            
            assert result is True  # App should continue even with unhealthy Kafka
            assert app.kafka_transport is not None


class TestMetadataExtractionAppStartup:
    """Test cases for application startup and running."""
    
    @pytest.mark.unit
    async def test_start_success(self):
        """Test successful application startup."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService') as mock_metadata_service, \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_metadata_instance = AsyncMock()
            mock_metadata_service.return_value = mock_metadata_instance
            
            mock_kafka_instance = AsyncMock()
            # Mock the transport service to complete quickly for testing
            async def mock_start():
                await asyncio.sleep(0.1)
                return True
            
            mock_kafka_instance.start = mock_start
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            
            # Start the app and trigger shutdown quickly
            async def trigger_shutdown():
                await asyncio.sleep(0.05)  # Let app start
                await app.shutdown()
            
            import asyncio
            startup_task = asyncio.create_task(app.start())
            shutdown_task = asyncio.create_task(trigger_shutdown())
            
            result, _ = await asyncio.gather(startup_task, shutdown_task)
            
            assert result is True
            assert app.running is False  # Should be False after shutdown

    @pytest.mark.unit
    async def test_start_failure_initialization(self):
        """Test startup failure due to initialization error."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.load.side_effect = Exception("Initialization failed")
        
        app = MetadataExtractionApp(config_loader=mock_loader)
        result = await app.start()
        
        assert result is False
        assert app.running is False

    @pytest.mark.unit
    async def test_start_handles_transport_error_gracefully(self):
        """Test that app handles transport errors gracefully."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService'), \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_kafka_instance = AsyncMock()
            # Make transport task fail
            async def failing_start():
                raise Exception("Transport failed")
            
            mock_kafka_instance.start = failing_start
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            
            # Trigger shutdown quickly
            async def trigger_shutdown():
                await asyncio.sleep(0.05)
                await app.shutdown()
            
            import asyncio
            startup_task = asyncio.create_task(app.start())
            shutdown_task = asyncio.create_task(trigger_shutdown())
            
            result, _ = await asyncio.gather(startup_task, shutdown_task)
            
            assert result is True  # App should correctly handle the failure
            assert app.running is False

    @pytest.mark.unit
    async def test_start_handles_task_cancellation(self):
        """Test that startup properly handles task cancellation."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService'), \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_kafka_instance = AsyncMock()
            # Mock transport to run indefinitely
            async def mock_start():
                try:
                    while True:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    raise
            
            mock_kafka_instance.start = mock_start
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            
            # Start the app and cancel after short delay
            async def trigger_shutdown():
                await asyncio.sleep(0.05)
                await app.shutdown()
            
            import asyncio
            startup_task = asyncio.create_task(app.start())
            shutdown_task = asyncio.create_task(trigger_shutdown())
            
            result, _ = await asyncio.gather(startup_task, shutdown_task)
            
            assert result is True


class TestMetadataExtractionAppSignalHandling:
    """Test cases for signal handling and graceful shutdown."""
    
    @pytest.mark.unit
    async def test_signal_handlers_registered_during_start(self):
        """Test that signal handlers are automatically registered during app.start()."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService'), \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_kafka_instance = AsyncMock()
            # Mock transport to complete quickly
            async def quick_transport():
                await asyncio.sleep(0.01)
                return True
            mock_kafka_instance.start = quick_transport
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            
            import signal
            # Store original handlers
            original_sigint = signal.getsignal(signal.SIGINT)
            
            try:
                # Signal handlers should not be registered before start()
                assert signal.getsignal(signal.SIGINT) == original_sigint
                
                # Start app and trigger quick shutdown
                async def trigger_shutdown():
                    await asyncio.sleep(0.05)  # Let initialization complete
                    
                    # Verify handlers are now registered
                    current_sigint = signal.getsignal(signal.SIGINT)
                    assert current_sigint != original_sigint, "SIGINT handler should be registered after start()"
                    
                    # Call the handler directly (simulating signal reception)
                    current_sigint(signal.SIGINT, None)
                    
                    # Verify the handler set the shutdown event
                    assert app._shutdown_event.is_set(), "Signal handler should set shutdown event"
                
                import asyncio
                startup_task = asyncio.create_task(app.start())
                test_task = asyncio.create_task(trigger_shutdown())
                
                result, _ = await asyncio.gather(startup_task, test_task)
                assert result is True
                
            finally:
                # Restore original handlers
                signal.signal(signal.SIGINT, original_sigint)

    @pytest.mark.unit
    async def test_signal_handler_behavior_during_runtime(self):
        """Test signal handler behavior during actual app runtime."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService'), \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_kafka_instance = AsyncMock()
            # Mock transport to run until shutdown
            async def transport_until_shutdown():
                while not app._shutdown_event.is_set():
                    await asyncio.sleep(0.01)
                return True
            mock_kafka_instance.start = transport_until_shutdown
            mock_kafka_service.return_value = mock_kafka_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            
            # Store original handlers
            original_sigint = signal.getsignal(signal.SIGINT)
            original_sigterm = signal.getsignal(signal.SIGTERM)
            
            try:
                async def test_signal_during_runtime():
                    await asyncio.sleep(0.05)  # Let app start and register handlers
                    
                    # Get the registered handler from the actual signal registry
                    registered_handler = signal.getsignal(signal.SIGINT)
                    assert registered_handler != original_sigint, "Handler should be registered"
                    
                    # Verify shutdown event is not set
                    assert not app._shutdown_event.is_set()
                    
                    # Simulate signal reception
                    registered_handler(signal.SIGINT, None)
                    
                    # Verify the app responds to the signal
                    assert app._shutdown_event.is_set(), "App should respond to signal"
                
                startup_task = asyncio.create_task(app.start())
                test_task = asyncio.create_task(test_signal_during_runtime())
                
                result, _ = await asyncio.gather(startup_task, test_task)
                assert result is True
                
            finally:
                # Restore original handlers
                signal.signal(signal.SIGINT, original_sigint)
                signal.signal(signal.SIGTERM, original_sigterm)

    @pytest.mark.unit
    async def test_both_signals_work_identically(self):
        """Test that both SIGINT and SIGTERM work identically."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService'), \
             patch('main.KafkaTransportService') as mock_kafka_service:
            
            mock_kafka_instance = AsyncMock()
            async def quick_start():
                await asyncio.sleep(0.01)
            mock_kafka_instance.start = quick_start
            mock_kafka_service.return_value = mock_kafka_instance
            
            import signal
            # Test both signals
            for sig, sig_name in [(signal.SIGINT, "SIGINT"), (signal.SIGTERM, "SIGTERM")]:
                app = MetadataExtractionApp(config_loader=mock_loader)
                original_handler = signal.getsignal(sig)
                
                try:
                    async def test_signal():
                        await asyncio.sleep(0.05)  # Let app initialize
                        
                        registered_handler = signal.getsignal(sig)
                        assert registered_handler != original_handler
                        
                        assert not app._shutdown_event.is_set()
                        registered_handler(sig, None)
                        assert app._shutdown_event.is_set(), f"{sig_name} handler should work"
                    
                    import asyncio
                    startup_task = asyncio.create_task(app.start())
                    test_task = asyncio.create_task(test_signal())
                    
                    await asyncio.gather(startup_task, test_task)
                    
                finally:
                    signal.signal(sig, original_handler)


class TestMetadataExtractionAppShutdown:
    """Test cases for application shutdown and cleanup."""
    
    @pytest.mark.unit
    async def test_shutdown_sets_event_and_stops_running(self):
        """Test that shutdown properly sets shutdown event and stops running state."""
        app = MetadataExtractionApp()
        app.running = True
        
        assert not app._shutdown_event.is_set()
        assert app.running is True
        
        await app.shutdown()
        
        assert app._shutdown_event.is_set()
        assert app.running is False

    @pytest.mark.unit
    async def test_cleanup_with_kafka_transport(self):
        """Test cleanup when Kafka transport is present."""
        mock_kafka_transport = AsyncMock()
        
        app = MetadataExtractionApp()
        app.kafka_transport = mock_kafka_transport
        
        await app.cleanup()
        
        mock_kafka_transport.stop.assert_called_once()

    @pytest.mark.unit
    async def test_cleanup_without_kafka_transport(self):
        """Test cleanup when no Kafka transport is present."""
        app = MetadataExtractionApp()
        app.kafka_transport = None
        
        # Should not raise any exceptions
        await app.cleanup()


class TestMainEntryPoints:
    """Test cases for main entry point functions."""
    
    @pytest.mark.unit
    async def test_main_async_success(self):
        """Test successful main_async execution."""
        from main import main_async
        
        mock_app = AsyncMock()
        mock_app.start.return_value = True
        
        # Should complete without raising exceptions
        await main_async(app=mock_app)
        
        mock_app.start.assert_called_once()

    @pytest.mark.unit
    async def test_main_async_failure(self):
        """Test main_async with application failure."""
        from main import main_async
        
        with pytest.raises(SystemExit) as exc_info:
            mock_app = AsyncMock()
            mock_app.start.return_value = False
            
            await main_async(app=mock_app)
        
        assert exc_info.value.code == 1

    @pytest.mark.unit
    async def test_main_async_keyboard_interrupt(self):
        """Test main_async handling KeyboardInterrupt."""
        from main import main_async
        
        mock_app = AsyncMock()
        mock_app.start.side_effect = KeyboardInterrupt()
        
        # Should handle KeyboardInterrupt gracefully
        await main_async(app=mock_app)

    @pytest.mark.unit
    async def test_main_async_unexpected_exception(self):
        """Test main_async handling unexpected exceptions."""
        from main import main_async
        
        with pytest.raises(SystemExit) as exc_info:
            mock_app = AsyncMock()
            mock_app.start.side_effect = RuntimeError("Unexpected error")
            
            await main_async(app=mock_app)
        
        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_main_sync_wrapper(self):
        """Test main sync wrapper function."""
        from main import main
        
        with patch('main.asyncio.run') as mock_asyncio_run:
            main()
            mock_asyncio_run.assert_called_once()


class TestErrorScenarios:
    """Test cases for various error scenarios."""
    
    @pytest.mark.unit
    async def test_metadata_service_check_failure(self):
        """Test handling of metadata service check failure during initialization."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.environment = "testing"
        mock_loader.config_dir = "/tmp/config"
        mock_config = create_mock_config()
        mock_loader.load.return_value = mock_config
        
        with patch('main.MetadataExtractionService') as mock_service, \
             patch('main.KafkaTransportService'):
            mock_instance = MagicMock()
            # Simulate failure in the service check
            mock_instance.config_data_model.get_supported_domains.side_effect = Exception("Check failed")
            mock_service.return_value = mock_instance
            
            app = MetadataExtractionApp(config_loader=mock_loader)
            result = await app.initialize()
            
            # Should still succeed initialization even if check fails
            assert result is True

    @pytest.mark.unit
    async def test_initialization_failure_no_config(self):
        """Test initialization failure when config loading fails."""
        mock_loader = MagicMock(spec=YamlFileConfigLoader)
        mock_loader.load.side_effect = RuntimeError("Config loading failed")
        
        app = MetadataExtractionApp(config_loader=mock_loader)
        result = await app.initialize()
        
        assert result is False