"""
Shared test fixtures for the archive generator test suite.
"""
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Generator
import pytest
import shutil

import importlib.util
from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel

HAS_KAFKA_PYTHON = importlib.util.find_spec("kafka") is not None

# Test configuration paths
TEST_DIR = Path(__file__).parent.parent
CONFIG_PATH = TEST_DIR / "integration" / "test_app_config.yaml"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def test_config_path() -> Path:
    """Path to the test configuration file."""
    return CONFIG_PATH


@pytest.fixture
def temp_archive_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test archives."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_archives_"))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config() -> ConfigDataModel:
    """Load test configuration using YamlFileConfigLoader."""
    return YamlFileConfigLoader().load()


@pytest.fixture
def config_with_temp_dir(config: ConfigDataModel, temp_archive_dir: Path) -> ConfigDataModel:
    """Configuration with temporary archive directory."""
    config.app.archive_directory = str(temp_archive_dir)
    if hasattr(config.app, 'storage') and hasattr(config.app.storage, 'backends'):
        if 'local_file' in config.app.storage.backends:
            config.app.storage.backends['local_file']['base_path'] = str(temp_archive_dir)
    return config


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock fixtures for unit tests
@pytest.fixture
def mock_config():
    """Mock configuration for unit tests."""
    from unittest.mock import Mock
    
    mock = Mock()
    mock.app.name = "test-archive-generator"
    mock.app.version = "1.0.0"
    mock.app.archive_directory = "/tmp/test-archives"
    mock.app.singlefile_binary_path = "/usr/bin/singlefile"
    
    # Mock Kafka config through transport structure
    kafka_config = Mock()
    kafka_config.bootstrap_servers = "localhost:9092"
    kafka_config.topics = {
        "archive_requests": "test.archive.requests",
        "archive_status": "test.archive.status",
        "archive_completed": "test.archive.completed",
        "archive_failed": "test.archive.failed"
    }
    kafka_config.consumer_group = "test-group"
    
    # Mock transport structure
    transport_mock = Mock()
    transport_mock.kafka = kafka_config
    transport_mock.enabled = ["kafka"]
    
    mock.app.transport = transport_mock
    mock.app.get_kafka_config.return_value = kafka_config
    
    return mock


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing with real config objects."""
    from configs.models import ConfigDataModel, DomainConfig, AppConfig, TransportConfig, KafkaConfig, StorageConfig
    
    return ConfigDataModel(
        domains=[
            DomainConfig(
                name="example.com",
                generators=[{"name": "scoop", "artifacts": ["warc", "screenshot"]}],
                webpage_types="dynamic"
            ),
            DomainConfig(
                name="static-site.org",
                generators=[{"name": "scoop", "artifacts": ["warc"]}],
                webpage_types="static"
            )
        ],
        app=AppConfig(
            name="test-archive-generator",
            version="1.0.0",
            transport=TransportConfig(
                enabled=["kafka"],
                kafka=KafkaConfig(
                    bootstrap_servers="localhost:9092",
                    topics={"archive_requests": "test.archive.requests"},
                    consumer_group="test-group"
                )
            ),
            storage=StorageConfig(
                enabled=["local_file"],
                backends={"local_file": {"base_path": "/tmp/archives"}}
            ),
            archive_directory="/tmp/archives",
            singlefile_binary_path="/usr/bin/singlefile"
        )
    )


@pytest.fixture
def kafka_config():
    """Create a Kafka configuration for testing."""
    from configs.models import ConfigDataModel, DomainConfig, AppConfig, KafkaConfig, TransportConfig, StorageConfig
    
    return ConfigDataModel(
        domains=[
            DomainConfig(
                name="example.com",
                generators=[{"name": "scoop", "artifacts": ["warc", "screenshot"]}],
                webpage_types="dynamic"
            )
        ],
        app=AppConfig(
            name="test-archive-generator",
            version="1.0.0",
            transport=TransportConfig(
                enabled=["kafka"],
                kafka=KafkaConfig(
                    bootstrap_servers="localhost:9092",
                    topics={
                        "archive_requests": "test.archive.requests",
                        "archive_status": "test.archive.status",
                        "archive_completed": "test.archive.completed",
                        "archive_failed": "test.archive.failed"
                    },
                    consumer_group="test-group"
                )
            ),
            storage=StorageConfig(
                enabled=["local_file"],
                backends={"local_file": {"base_path": "/tmp/archives"}}
            ),
            archive_directory="/tmp/archives",
            singlefile_binary_path="/usr/bin/singlefile"
        )
    )


@pytest.fixture
def mock_kafka_producer():
    """Create a mock Kafka producer."""
    from unittest.mock import Mock
    
    producer = Mock()
    future = Mock()
    future.get.return_value = None  # Simulate successful send
    producer.send.return_value = future
    return producer


# End of file
