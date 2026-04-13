import pytest
import os
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from configs import YamlFileConfigLoader
from app.storage import create_storage_service

@pytest.fixture(scope="session")
def test_env():
    """Create a temporary environment for the entire test session."""
    temp_dir = tempfile.mkdtemp()
    # Ensure logs/archives/data dirs exist in temp_dir
    Path(temp_dir, "logs").mkdir(parents=True, exist_ok=True)
    Path(temp_dir, "archives").mkdir(parents=True, exist_ok=True)
    Path(temp_dir, "data").mkdir(parents=True, exist_ok=True)
    
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture(scope="session")
def session_app_config(test_env):
    """Load and cache the app configuration for the entire session."""
    loader = YamlFileConfigLoader()
    config = loader.load()
    
    # Disable Kafka for all tests by default
    config.transport.kafka_enabled = False
    
    # Use temp directory for all storage
    config.storage.type = 'sqlite'
    config.storage.filesystem.path = test_env
    
    # Ensure sqlite config exists
    if not hasattr(config.storage, 'sqlite') or not config.storage.sqlite:
        from configs.models import SQLiteConfig
        config.storage.sqlite = SQLiteConfig()
    
    config.storage.sqlite.db_path = str(Path(test_env) / "test_archive_web.db")
    
    # Override directories to use temp_dir if needed
    config.directories.logs = str(Path(test_env) / "logs")
    config.directories.archives = str(Path(test_env) / "archives")
    config.directories.data = str(Path(test_env) / "data")
    
    return config

@pytest.fixture(scope="session", autouse=True)
def mock_kafka_globally():
    """Globally mock KafkaProducerService.initialize to avoid timeouts."""
    with patch("app.services.kafka_producer.KafkaProducerService.initialize", return_value=True):
        yield

@pytest.fixture(scope="session")
def shared_app(session_app_config):
    """Provide a shared application instance with test configuration."""
    # Patch the app state with the session-scoped config
    app.state.app_config = session_app_config
    
    # Initialize storage once for the session
    storage_service = create_storage_service(session_app_config)
    app.state.storage_service = storage_service
    
    return app

@pytest.fixture
def client(shared_app):
    """Standard client fixture that reuses the shared app."""
    with TestClient(shared_app) as c:
        yield c
