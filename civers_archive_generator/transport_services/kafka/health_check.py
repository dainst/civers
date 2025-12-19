# health_check.py
import asyncio
import logging
import subprocess
import time
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from configs.loaders import YamlFileConfigLoader
from configs.logging_config import setup_logging, get_logger
from transport_services.kafka.kafka_transport_service import KafkaTransportService

# Configure logging with Kafka suppression
setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger(__name__)

class SystemHealthCheck:
    """Check the health of all system components."""
    
    def __init__(self, environment="development"):
        self.config = None
        self.checks_passed = 0
        self.total_checks = 0
        self.environment = environment

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
            # Set environment variable for this loader instance
            original_env = os.getenv("ARCHIVE_ENV")
            os.environ["ARCHIVE_ENV"] = self.environment
            try:
                self.config = YamlFileConfigLoader().load()
            finally:
                # Restore original environment variable
                if original_env is not None:
                    os.environ["ARCHIVE_ENV"] = original_env
                elif "ARCHIVE_ENV" in os.environ:
                    del os.environ["ARCHIVE_ENV"]
            
            logger.info("✅ Configuration loaded successfully")
            logger.info(f"   - Environment: {self.environment}")
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
            from archive_services import ArchiveService
            archive_service = ArchiveService(self.config)
            transport_service = KafkaTransportService(self.config, archive_service)
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
            from archive_services import ArchiveService
            archive_service = ArchiveService(self.config)
            transport_service = KafkaTransportService(self.config, archive_service)
            # Just check that we can create the service (consumer is created on start)
            await transport_service.stop()
            logger.info("✅ Kafka transport service consumer can be created")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Kafka transport service consumer creation failed: {e}")
            return False
    
    def check_archive_directory(self) -> bool:
        """Check if archive directory exists and is writable."""
        self.total_checks += 1
        try:
            import os
            archive_dir = self.config.app.archive_directory
            
            # Create directory if it doesn't exist
            os.makedirs(archive_dir, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(archive_dir, "test_write_access.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            logger.info(f"✅ Archive directory is accessible: {archive_dir}")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"❌ Archive directory check failed: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """Check if required Python packages are available."""
        self.total_checks += 1
        required_packages = [
            'kafka',
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
    
    async def run_health_check(self) -> bool:
        """Run all health checks."""
        logger.info("🏥 Running System Health Check")
        logger.info("=" * 50)
        
        # Check dependencies first
        self.check_dependencies()
        
        # Check Docker and Kafka
        self.check_docker_kafka()
        
        # Check configuration
        if not self.check_config_loading():
            logger.error("❌ Cannot proceed without valid configuration")
            return False
        
        # Check Kafka components
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

async def main(environment="development"):
    """Run health check."""
    health_check = SystemHealthCheck(environment=environment)
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

if __name__ == "__main__":
    print("🏥 System Health Check")
    environment = "development"
    # check if debug mode is enabled
    import os
    debug_mode = os.getenv("UV_LOG_LEVEL", "false").lower() == "debug"
    if debug_mode:
        logger.debug("Debug mode is enabled. Using testing environment.")
        environment = "testing"
    else:
        logger.info("Debug mode is disabled. Using development environment.")
    logger.info(f"Using environment: {environment}")
    logger.info("=" * 50)
    # Run the health check
    asyncio.run(main(environment=environment))