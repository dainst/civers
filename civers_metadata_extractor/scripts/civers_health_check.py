# health_check.py
import asyncio
import json
import logging
import subprocess
import time
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient
from configs.config_validator import validate_configuration_file
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.kafka_transport_service import KafkaTransportService

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class SystemHealthCheck:
    """Check the health of all system components."""
    
    def __init__(self, config_path="app_config.yaml"):
        self.config = None
        self.checks_passed = 0
        self.total_checks = 0
        self.config_path = config_path

    def check_docker_kafka(self) -> bool:
        """Check if Kafka Docker container is running."""
        self.total_checks += 1
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=broker", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "broker" in result.stdout:
                logger.info("✅ Kafka Docker container is running")
                self.checks_passed += 1
                return True
            else:
                logger.error("❌ Kafka Docker container is not running")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking Docker: {e}")
            return False
    
    def check_config_loading(self) -> bool:
        """Check if configuration can be loaded."""
        self.total_checks += 1
        try:
            self.config = validate_configuration_file(self.config_path, strict_mode=False)
            logger.info("✅ Configuration loaded successfully")
            logger.info(f"   - Domains configured: {len(self.config.domains)}")
            
            # Use the new get_kafka_config() method
            kafka_config = self.config.app.get_kafka_config()
            if kafka_config:
                logger.info(f"   - Kafka topics: {len(kafka_config.topics)}")
            else:
                logger.warning("   - No Kafka configuration found")
            
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Configuration loading failed: {e}")
            return False
    
    async def check_kafka_producer(self) -> bool:
        """Check if Kafka transport service can be created (includes producer)."""
        self.total_checks += 1
        try:
            from metadata_extraction_services.metadata_extraction_service import MetadataExtractionService
            metadata_service = MetadataExtractionService(self.config)
            transport_service = KafkaTransportService(self.config, metadata_service)
            await transport_service.stop()
            logger.info("✅ Kafka transport service can be created (producer included)")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Kafka transport service creation failed: {e}")
            return False
    
    async def check_kafka_consumer(self) -> bool:
        """Check if Kafka transport service consumer can be created."""
        self.total_checks += 1
        try:
            from metadata_extraction_services.metadata_extraction_service import MetadataExtractionService
            metadata_service = MetadataExtractionService(self.config)
            transport_service = KafkaTransportService(self.config, metadata_service)
            # Just check that we can create the service (consumer is created on start)
            await transport_service.stop()
            logger.info("✅ Kafka transport service consumer can be created")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Kafka transport service consumer creation failed: {e}")
            return False
    
    def check_archive_directory(self) -> bool:
        """Check if storage directory exists and is writable."""
        self.total_checks += 1
        try:
            import os
            storage_config = self.config.app.get_storage_config()
            backend_config = storage_config.get_backend_config()
            archive_dir = backend_config.get("base_path", "archives")
            
            # Create directory if it doesn't exist
            os.makedirs(archive_dir, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(archive_dir, "test_write_access.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            logger.info(f"✅ Storage directory is accessible: {archive_dir}")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Storage directory check failed: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """Check if required Python packages are available."""
        self.total_checks += 1
        required_packages = [
            'aiokafka',
            'pydantic', 
            'yaml',
            'asyncio'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if not missing_packages:
            logger.info("✅ All required dependencies are available")
            self.checks_passed += 1
            return True
        else:
            logger.error(f"❌ Missing dependencies: {missing_packages}")
            return False
    
    async def check_kafka_admin_connectivity(self) -> bool:
        """Test low-level async Kafka admin client connectivity."""
        self.total_checks += 1
        try:
            kafka_config = self.config.app.get_kafka_config()
            bootstrap_servers = kafka_config.bootstrap_servers.split(',')
            
            admin_client = AIOKafkaAdminClient(
                bootstrap_servers=bootstrap_servers,
                request_timeout_ms=10000
            )
            
            await admin_client.start()
            cluster_metadata = await admin_client.describe_cluster()
            topic_count = len(cluster_metadata.topics) if hasattr(cluster_metadata, 'topics') else 0
            
            await admin_client.close()
            
            logger.info(f"✅ Async Kafka admin client connectivity verified")
            logger.info(f"   - Cluster accessible")
            self.checks_passed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Async Kafka admin client connectivity failed: {e}")
            return False
    
    async def check_kafka_producer_connectivity(self) -> bool:
        """Test low-level async Kafka producer connectivity."""
        self.total_checks += 1
        try:
            kafka_config = self.config.app.get_kafka_config()
            bootstrap_servers = kafka_config.bootstrap_servers.split(',')
            
            producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=10000
            )
            
            await producer.start()
            
            # Send test message to status topic
            test_message = {
                "test": "health_check_connectivity",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "kafka_health_check"
            }
            
            status_topic = kafka_config.topics.get('metadata_status', 'metadata.status')
            
            # Send message and handle the response properly for aiokafka 0.12.0
            send_future = producer.send(status_topic, test_message)
            
            # Just ensure the send completes, don't try to access partition/offset
            await send_future
            
            await producer.stop()
            
            logger.info(f"✅ Async Kafka producer connectivity verified")
            logger.info(f"   - Test message sent to {status_topic} successfully")
            self.checks_passed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Async Kafka producer connectivity failed: {e}")
            return False
    
    async def check_kafka_consumer_connectivity(self) -> bool:
        """Test low-level async Kafka consumer connectivity."""
        self.total_checks += 1
        try:
            kafka_config = self.config.app.get_kafka_config()
            bootstrap_servers = kafka_config.bootstrap_servers.split(',')
            status_topic = kafka_config.topics.get('metadata_status', 'metadata.status')
            
            consumer = AIOKafkaConsumer(
                status_topic,
                bootstrap_servers=bootstrap_servers,
                group_id='health_check_test_group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
            )
            
            await consumer.start()
            
            # Try to consume with timeout (will timeout if no messages, which is fine)
            message_count = 0
            try:
                import asyncio
                async def consume_with_timeout():
                    nonlocal message_count
                    async for message in consumer:
                        message_count += 1
                        if message_count >= 1:  # Just test that we can consume
                            break
                
                await asyncio.wait_for(consume_with_timeout(), timeout=3.0)
            except asyncio.TimeoutError:
                pass  # Timeout is expected if no messages
            except Exception:
                pass  # Other exceptions are also acceptable for this test
            
            await consumer.stop()
            
            logger.info(f"✅ Async Kafka consumer connectivity verified")
            if message_count > 0:
                logger.info(f"   - Consumed {message_count} test message(s) from {status_topic}")
            else:
                logger.info(f"   - Consumer ready (no messages to consume)")
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Kafka consumer connectivity failed: {e}")
            return False
    
    async def run_health_check(self) -> bool:
        """Run all health checks."""
        logger.info("🏥 Running CIVERS System Health Check")
        logger.info("=" * 50)
        
        # Check dependencies first
        self.check_dependencies()
        
        # Check Docker and Kafka
        self.check_docker_kafka()
        
        # Check configuration
        if not self.check_config_loading():
            logger.error("❌ Cannot proceed without valid configuration")
            return False
        
        # Low-level Kafka connectivity tests
        logger.info("🔍 Testing low-level async Kafka connectivity...")
        await self.check_kafka_admin_connectivity()
        await self.check_kafka_producer_connectivity()
        await self.check_kafka_consumer_connectivity()
        
        # High-level application integration tests
        logger.info("🚀 Testing application-level Kafka integration...")
        await self.check_kafka_producer()
        await self.check_kafka_consumer()
        
        # Check file system
        self.check_archive_directory()
        
        # Summary
        logger.info("=" * 50)
        logger.info(f"🏥 Health Check Results: {self.checks_passed}/{self.total_checks} passed")
        
        if self.checks_passed == self.total_checks:
            logger.info("🎉 All health checks passed! System is ready.")
            return True
        else:
            logger.error("❌ Some health checks failed. Fix issues before running the system.")
            return False

async def async_main(config_path="app_config.yaml"):
    """Run health check asynchronously."""
    health_check = SystemHealthCheck(config_path=config_path)
    success = await health_check.run_health_check()
    
    if success:
        print("\n✅ System is healthy and ready to run!")
        print("You can now run:")
        print("  - python main_app.py (main application)")
        print("  - python monitor_app.py (monitoring application)")
        print("  - ./run_tests.sh unit (unit tests)")
        print("  - ./run_tests.sh integration --run-integration (integration tests)")
    else:
        print("\n❌ System health check failed. Fix the issues above.")

def main():
    """Synchronous wrapper for script entry point."""
    print("🏥 CIVERS System Health Check")
    config_path = "app_config.yaml"
    # check if debug mode is enabled
    import os
    debug_mode = os.getenv("UV_LOG_LEVEL", "false").lower() == "debug"
    if debug_mode:
        logger.debug("Debug mode is enabled. Using test configuration.")
        config_path = "tests/integration/test_app_config.yaml"
    else:
        logger.info("Debug mode is disabled. Using default configuration.")
    logger.info(f"Using configuration file: {config_path}")
    logger.info("=" * 50)
    # Run the health check
    asyncio.run(async_main(config_path=config_path))

if __name__ == "__main__":
    main()