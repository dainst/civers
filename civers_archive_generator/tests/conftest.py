# tests/conftest.py
"""
Pytest configuration and shared fixtures for the archive generator test suite.
This file imports shared fixtures and configures the test environment.
"""
import pytest
import tempfile
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import shared fixtures from the fixtures package
from tests.fixtures.shared_fixtures import *

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Pytest markers configuration
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "browser: marks tests that require browser automation"
    )
    config.addinivalue_line(
        "markers", "kafka: marks tests that require Kafka infrastructure"
    )

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests"
    )
    parser.addoption(
        "--run-slow",
        action="store_true", 
        default=False,
        help="Run slow tests"
    )

def pytest_collection_modifyitems(config, items):
    """Automatically skip tests that require external dependencies."""
    for item in items:
        # Skip integration tests unless explicitly run
        if "integration" in item.keywords and not config.getoption("--run-integration", default=False):
            item.add_marker(pytest.mark.skip(reason="Integration test skipped (use --run-integration to run)"))
        
        # Skip e2e tests unless explicitly run
        if "e2e" in item.keywords and not config.getoption("--run-e2e", default=False):
            item.add_marker(pytest.mark.skip(reason="E2E test skipped (use --run-e2e to run)"))
        
        # Skip slow tests unless explicitly run
        if "slow" in item.keywords and not config.getoption("--run-slow", default=False):
            item.add_marker(pytest.mark.skip(reason="Slow test skipped (use --run-slow to run)"))
        
        # Skip browser tests if playwright not available
        if "browser" in item.keywords:
            try:
                import playwright
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="Playwright not installed"))

@pytest.fixture(scope="session")
def test_data_dir():
    """
    Session-scoped fixture providing a test data directory.
    
    This directory can be used to store test fixtures, sample files,
    and other test-related data that needs to persist across tests.
    """
    test_dir = Path(__file__).parent / "test_data"
    test_dir.mkdir(exist_ok=True)
    return test_dir

@pytest.fixture
def temp_dir():
    """
    Function-scoped fixture providing a temporary directory.
    
    This directory is automatically cleaned up after each test.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def temp_archive_dir():
    """Create temporary directory for archive testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def mock_config_dict():
    """Sample configuration dictionary for testing."""
    return {
        "app": {
            "name": "test_archive_generator",
            "version": "1.0.0",
            "transport": {
                "enabled": ["kafka"],
                "kafka": {
                    "bootstrap_servers": "localhost:9092",
                    "topics": {
                        "archive_requests": "test.requests",
                        "archive_status": "test.status",
                        "archive_completed": "test.completed", 
                        "archive_failed": "test.failed"
                    },
                    "consumer_group": "test_group"
                }
            },
            "storage": {
                "enabled": ["local_file"],
                "backends": {
                    "local_file": {"base_path": "test_archives"}
                }
            },
            "archive_directory": "test_archives",
            "singlefile_binary_path": "/usr/bin/singlefile"
        },
        "domains": [
            {
                "name": "example.com",
                "artifacts": ["warc", "html"],
                "webpage_types": "dynamic"
            }
        ]
    }

@pytest.fixture
def valid_config_dict():
    """Valid configuration dictionary for testing config loading."""
    return {
        "domains": [
            {
                "name": "example.com",
                "artifacts": ["warc", "html"],
                "webpage_types": "dynamic"
            },
            {
                "name": "test.org", 
                "artifacts": ["warc"],
                "webpage_types": "static"
            }
        ],
        "app": {
            "name": "test_archive_generator",
            "version": "1.0.0",
            "archive_directory": "/tmp/test_archives",
            "singlefile_binary_path": "/usr/bin/singlefile",
            "transport": {
                "enabled": ["kafka"],
                "kafka": {
                    "bootstrap_servers": "localhost:9092",
                    "consumer_group": "test_consumers",
                    "topics": {
                        "archive_requests": "archive_requests",
                        "archive_status": "archive_status"
                    }
                }
            },
            "storage": {
                "enabled": ["local_file"],
                "backends": {
                    "local_file": {"base_path": "/tmp/test_archives"}
                }
            }
        }
    }

@pytest.fixture
def mock_config(temp_archive_dir, mock_config_dict):
    """Create a proper ConfigDataModel instance for testing."""
    try:
        from configs.models import ConfigDataModel
        
        # Update paths to use temp directory
        mock_config_dict["app"]["archive_directory"] = temp_archive_dir
        mock_config_dict["app"]["sqlite"]["db_path"] = os.path.join(temp_archive_dir, "test.db")
        
        # Create config from dict
        config = ConfigDataModel(**mock_config_dict)
        return config
    except ImportError as e:
        pytest.skip(f"Could not import ConfigDataModel: {e}")

@pytest.fixture
def sample_http_entries():
    """Sample HTTP entries for testing WARC functionality."""
    return [
        {
            'type': 'request',
            'url': 'https://example.com/',
            'method': 'GET',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            },
            'post_data': None,
            'timestamp': '2025-06-20T10:30:00.123456',
            'resource_type': 'document'
        },
        {
            'type': 'response',
            'url': 'https://example.com/',
            'status': 200,
            'status_text': 'OK',
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Length': '1234'
            },
            'body': b'<!DOCTYPE html><html><head><title>Test</title></head><body>Hello</body></html>',
            'timestamp': '2025-06-20T10:30:00.456789'
        }
    ]

@pytest.fixture
def mock_singlefile_binary(temp_dir):
    """Create a mock SingleFile binary for testing."""
    mock_binary = Path(temp_dir) / "single-file"
    mock_binary.write_text("#!/bin/bash\necho 'Mock SingleFile'\n")
    mock_binary.chmod(0o755)
    return str(mock_binary)

