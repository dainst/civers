"""Common configuration fixtures and the opt-in integration test flag."""

import os
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ.setdefault("CONFIG_ENVIRONMENT", "testing")


@pytest.fixture(autouse=True)
def set_testing_env(monkeypatch):
    """Isolate environment selection from the developer's shell."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample configuration for testing with real config objects."""
    from configs.models import (
        AppConfig,
        ConfigDataModel,
        DomainConfig,
        StorageConfig,
        TransportConfig,
    )

    return ConfigDataModel(
        domains=[
            DomainConfig(
                name="example.com",
                generators=[{"name": "scoop", "artifacts": ["warc", "screenshot"]}],
                webpage_types="dynamic",
            ),
            DomainConfig(
                name="static-site.org",
                generators=[{"name": "scoop", "artifacts": ["warc"]}],
                webpage_types="static",
            ),
        ],
        transport=TransportConfig(
            enabled=["kafka"],
            transports={
                "kafka": {
                    "bootstrap_servers": "localhost:9092",
                    "topics": {"archive_requests": "test.archive.requests"},
                    "consumer_group": "test-group",
                }
            },
        ),
        app=AppConfig(
            name="test-archive-generator",
            version="1.0.0",
            storage=StorageConfig(),
            archive_directory=str(tmp_path / "archives"),
            singlefile_binary_path="/usr/bin/singlefile",
        ),
    )


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests requiring an external Kafka broker",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(
        reason="Use --run-integration to run Kafka integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
