"""
pytest configuration and shared fixtures for CiVers ChangeDetection.
"""

import os
from pathlib import Path

import pytest
from configs.loaders import YamlFileConfigLoader

# Force testing environment before any imports that load config
os.environ.setdefault("CONFIG_ENVIRONMENT", "testing")


@pytest.fixture(autouse=True)
def set_testing_env(monkeypatch):
    """Ensure CONFIG_ENVIRONMENT=testing for every test."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")


@pytest.fixture
def testing_config():
    """
    Load a real ConfigDataModel from the testing.yaml environment.
    Tests that use this fixture must be run from inside the component directory
    (or have the component root on PYTHONPATH).
    """
    loader = YamlFileConfigLoader(environment="testing")
    return loader.load()


@pytest.fixture
def sample_request_data():
    """Minimal valid request event payload."""
    return {
        "request_id": "test-request-001",
        "url": "https://example.com/resource",
        "metadata": {},
    }


@pytest.fixture
def sample_kafka_config_dict():
    """Minimal Kafka configuration dict for unit tests."""
    return {
        "bootstrap_servers": "localhost:29092",
        "consumer_group": "change_detection_group_test",
        "topics": {
            "requests": "change.detection.requests",
        },
    }
