"""
True End-to-End (E2E) tests for the complete Archive Generator Application.

These tests initialize and test the complete ArchiveGeneratorApp as users would experience it.
They test the full application lifecycle: startup → message processing → shutdown.

Unlike integration tests that test individual components, these E2E tests verify
that the complete system works together as a cohesive application.
"""
import asyncio
import json
import logging
import os
import tempfile
import pytest
from pathlib import Path
from kafka import KafkaProducer
from kafka.errors import KafkaError
import time

from main import ArchiveGeneratorApp
from transport_services.kafka.event_models import ArchiveRequestEvent

# Configure logging for E2E tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration file path
TEST_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'integration', 'test_app_config.yaml')


class TestCompleteApplicationE2E:
    """True End-to-End tests for the complete Archive Generator Application."""
    
    @pytest.fixture
    def temp_archive_dir(self):
        """Create a temporary directory for E2E test archives."""
        temp_dir = tempfile.mkdtemp(prefix="e2e_archives_")
        yield temp_dir
        # Cleanup after test
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def e2e_config_file(self, temp_archive_dir):
        """Create a temporary config file for E2E testing."""
        # Read the base test config
        import yaml
        with open(TEST_CONFIG_PATH, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Update paths to use temp directory
        config_data['app']['archive_directory'] = temp_archive_dir
        
        # Add httpbin.org domain for E2E testing
        config_data['domains'].append({
            'name': 'httpbin.org',
            'artifacts': ['warc', 'screenshots', 'html', 'singlefile'],
            'webpage_types': 'dynamic'
        })
        
        # Create temporary config file
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_config, default_flow_style=False)
        temp_config.close()
        
        yield temp_config.name
        
        # Cleanup
        os.unlink(temp_config.name)
    
    def _create_kafka_producer(self):
        """Create a Kafka producer for sending test messages."""
        return KafkaProducer(
            bootstrap_servers=['localhost:29093'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    async def _wait_for_archive_completion(self, archive_dir: str, request_id: str, timeout: int = 30) -> bool:
        """Wait for archive completion by checking the filesystem."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Look for directories containing the request_id
            for root, dirs, files in os.walk(archive_dir):
                if request_id in root and 'archive_metadata.json' in files:
                    logger.info(f"✅ Archive found for request {request_id}: {root}")
                    return True
            
            await asyncio.sleep(0.5)  # Check every 500ms
        
        logger.warning(f"⏰ Timeout waiting for archive completion: {request_id}")
        return False
    
    @pytest.mark.e2e
    @pytest.mark.integration
    @pytest.mark.kafka
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_complete_application_lifecycle(self, e2e_config_file, kafka_container, temp_archive_dir):
        """Test complete application lifecycle: startup → processing → shutdown."""
        
        # Initialize the complete application
        app = ArchiveGeneratorApp(config_path=e2e_config_file)
        
        # Test application initialization
        initialization_success = await app.initialize()
        assert initialization_success, "Application initialization failed"
        
        assert app.config is not None, "Configuration not loaded"
        assert app.kafka_transport is not None, "Kafka transport not initialized"
        
        # Verify health check
        health = await app.kafka_transport.health_check()
        assert health['healthy'], f"Health check failed: {health}"
        
        logger.info("✅ Application initialized successfully for E2E test")
        
        # Test graceful shutdown
        await app.cleanup()
        logger.info("✅ Application lifecycle test completed")
    
    @pytest.mark.e2e
    @pytest.mark.integration
    @pytest.mark.kafka
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_complete_kafka_message_processing_e2e(self, e2e_config_file, kafka_container, temp_archive_dir):
        """Test complete end-to-end workflow: Kafka message → archive creation."""
        
        # Initialize the complete application
        app = ArchiveGeneratorApp(config_path=e2e_config_file)
        await app.initialize()
        
        try:
            # Create a unique request for this E2E test
            request_id = f"e2e-test-{int(time.time())}"
            test_url = "https://httpbin.org/html"
            
            # Start the application in background
            logger.info("🚀 Starting complete application for E2E test")
            app_task = asyncio.create_task(app.start())
            
            # Give the application more time to start up and for Kafka topics to be ready
            await asyncio.sleep(5)
            
            # Send a real Kafka message to trigger processing
            logger.info(f"📤 Sending Kafka message for E2E test: {request_id}")
            
            try:
                producer = self._create_kafka_producer()
                
                # Create archive request event
                archive_request = {
                    "url": test_url,
                    "priority": 1,
                    "request_id": request_id,
                    "timestamp": time.time()
                }
                
                # Send message to Kafka
                future = producer.send('archive.requests', value=archive_request, key=request_id)
                producer.flush()  # Ensure message is sent
                
                record_metadata = future.get(timeout=10)
                logger.info(f"✅ Message sent to Kafka: topic={record_metadata.topic}, partition={record_metadata.partition}")
                
            except KafkaError as e:
                pytest.skip(f"Failed to send Kafka message: {e}")
            finally:
                producer.close()
            
            # Wait for the application to process the message and create archive
            logger.info(f"⏳ Waiting for archive completion: {request_id}")
            archive_completed = await self._wait_for_archive_completion(temp_archive_dir, request_id, timeout=120)
            
            assert archive_completed, f"Archive was not created within timeout for request {request_id}"
            
            # If archive was completed, give a bit more time for any cleanup to finish
            if archive_completed:
                logger.info("✅ Archive completed, waiting for any final processing...")
                await asyncio.sleep(3)
            
            # Verify the complete archive was created
            archive_found = False
            for root, dirs, files in os.walk(temp_archive_dir):
                if request_id in root:
                    # Verify expected files exist
                    expected_files = ['archive_metadata.json', 'screenshot.png', 'page_source.html', 'archive.warc']
                    for expected_file in expected_files:
                        file_path = os.path.join(root, expected_file)
                        assert os.path.exists(file_path), f"Missing expected file: {expected_file}"
                        assert os.path.getsize(file_path) > 0, f"Empty file: {expected_file}"
                    
                    # Verify metadata content
                    metadata_path = os.path.join(root, 'archive_metadata.json')
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    assert metadata['archive_info']['url'] == test_url
                    assert metadata['archive_info']['request_id'] == request_id
                    assert 'processing_time_seconds' in metadata['archive_info']
                    
                    archive_found = True
                    logger.info(f"✅ Complete archive verified: {root}")
                    break
            
            assert archive_found, f"No archive directory found for request {request_id}"
            
            logger.info("✅ Complete E2E Kafka workflow test passed!")
            
        finally:
            # Graceful shutdown
            await app.shutdown()
            
            # Wait a bit for shutdown to complete
            try:
                await asyncio.wait_for(app_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Application shutdown timed out")
                app_task.cancel()
            
            await app.cleanup()
    
    @pytest.mark.e2e
    @pytest.mark.integration
    @pytest.mark.kafka
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_application_error_handling_e2e(self, e2e_config_file, kafka_container, temp_archive_dir):
        """Test complete application error handling in E2E scenario."""
        
        # Initialize the complete application
        app = ArchiveGeneratorApp(config_path=e2e_config_file)
        await app.initialize()
        
        try:
            request_id = f"e2e-error-test-{int(time.time())}"
            invalid_url = "https://this-domain-definitely-does-not-exist-12345.com"
            
            # Start the application
            app_task = asyncio.create_task(app.start())
            await asyncio.sleep(2)  # Let it start
            
            # Send message with invalid URL
            logger.info(f"📤 Sending invalid URL for error handling test: {request_id}")
            
            try:
                producer = self._create_kafka_producer()
                
                archive_request = {
                    "url": invalid_url,
                    "priority": 1,
                    "request_id": request_id,
                    "timestamp": time.time()
                }
                
                future = producer.send('archive.requests', value=archive_request, key=request_id)
                producer.flush()
                future.get(timeout=10)
                
                logger.info("✅ Error handling message sent to Kafka")
                
            except KafkaError as e:
                pytest.skip(f"Failed to send Kafka message: {e}")
            finally:
                producer.close()
            
            # Wait a reasonable time for processing attempt
            await asyncio.sleep(15)
            
            # Verify that the application is still running and healthy after error
            health = await app.kafka_transport.health_check()
            assert health['healthy'], "Application should remain healthy after processing error"
            
            logger.info("✅ Application remained healthy after error processing")
            
        finally:
            await app.shutdown()
            try:
                await asyncio.wait_for(app_task, timeout=10)
            except asyncio.TimeoutError:
                app_task.cancel()
            await app.cleanup()
    
    @pytest.mark.e2e
    @pytest.mark.integration
    @pytest.mark.kafka
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_application_shutdown_signals_e2e(self, e2e_config_file, kafka_container):
        """Test complete application graceful shutdown via signals."""
        
        # Initialize the complete application
        app = ArchiveGeneratorApp(config_path=e2e_config_file)
        await app.initialize()
        
        try:
            # Start the application
            app_task = asyncio.create_task(app.start())
            await asyncio.sleep(1)  # Let it start
            
            # Test graceful shutdown via app.shutdown() (simulates signal handling)
            logger.info("🛑 Testing graceful shutdown")
            await app.shutdown()
            
            # Wait for application to shut down
            try:
                await asyncio.wait_for(app_task, timeout=15)
                logger.info("✅ Application shut down gracefully")
            except asyncio.TimeoutError:
                pytest.fail("Application failed to shutdown within timeout")
                
        finally:
            if not app_task.done():
                app_task.cancel()
            await app.cleanup()


# End of file
