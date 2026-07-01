# tests/conftest.py
"""
Pytest configuration and shared fixtures for the archive generator test suite.
"""
import logging
import os
import sys
import tempfile
import socket
import subprocess
import time
from pathlib import Path

import pytest
from kafka import KafkaAdminClient

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import shared fixtures from the fixtures package after sys.path is updated
from tests.fixtures.shared_fixtures import *  # noqa: E402, F401, F403

# Force testing environment before any module-level config loading
os.environ.setdefault("CONFIG_ENVIRONMENT", "testing")

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@pytest.fixture(autouse=True)
def set_testing_env(monkeypatch):
    """Ensure CONFIG_ENVIRONMENT=testing is set for every test."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "testing")


@pytest.fixture
def testing_config():
    """
    Load a real ConfigDataModel from the testing.yaml environment.
    Mirrors the same fixture in civers_change_detection/tests/conftest.py.
    """
    from configs.loaders import YamlFileConfigLoader
    return YamlFileConfigLoader(environment="testing").load()

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
            import importlib.util
            if importlib.util.find_spec("playwright") is None:
                item.add_marker(pytest.mark.skip(reason="Playwright not installed"))

@pytest.fixture(scope="session")
def test_data_dir():
    """
    Session-scoped fixture providing a test data directory.
    """
    test_dir = Path(__file__).parent / "test_data"
    test_dir.mkdir(exist_ok=True)
    return test_dir

@pytest.fixture
def temp_dir():
    """
    Function-scoped fixture providing a temporary directory.
    """
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
                "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
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
                "generators": [{"name": "scoop", "artifacts": ["warc", "html"]}],
                "webpage_types": "dynamic"
            },
            {
                "name": "test.org", 
                "generators": [{"name": "scoop", "artifacts": ["warc"]}],
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


def run_docker_compose_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a docker compose command."""
    full_command = ["docker", "compose"] + command
    return subprocess.run(
        full_command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=30
    )


def check_kafka_available(bootstrap_servers: str, timeout_seconds: float = 3.0) -> bool:
    """Check if Kafka is available and accepting connections."""
    try:
        host, port = bootstrap_servers.split(":")[0], int(bootstrap_servers.split(":")[1])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_seconds)
        result = sock.connect_ex((host, port))
        sock.close()

        if result != 0:
            return False

        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="health-check-ag",
            request_timeout_ms=int(timeout_seconds * 1000),
            api_version_auto_timeout_ms=int(timeout_seconds * 1000),
        )

        admin_client.list_topics()
        admin_client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def integration_kafka_config() -> ConfigDataModel:
    """Load config for integration tests."""
    from configs.loaders import YamlFileConfigLoader
    return YamlFileConfigLoader(environment="testing").load()


@pytest.fixture(scope="session")
def auto_start_kafka(integration_kafka_config: ConfigDataModel):
    """Auto-start Kafka broker container via docker compose."""
    auto_start = os.getenv("AUTO_START_KAFKA", "true").lower() == "true"
    if not auto_start:
        print("⏭️  AUTO_START_KAFKA=false - Skipping automatic Kafka startup")
        yield
        return

    project_root = Path(__file__).parent.parent

    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker Compose not available. Install Docker to run integration tests.")
        return

    compose_file = project_root / "docker-compose.yml"
    if not compose_file.exists():
        pytest.skip(f"docker-compose.yml not found at {compose_file}")
        return

    bootstrap_servers = integration_kafka_config.app.get_kafka_config().bootstrap_servers
    print("\n🚀 Starting Kafka broker container via docker compose...")
    print(f"   Bootstrap servers: {bootstrap_servers}")

    try:
        result = run_docker_compose_command(["up", "-d", "broker"], cwd=project_root)
        print("✅ Docker compose up broker completed")
        if result.stdout:
            print(f"   {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Kafka broker: {e.stderr}")
        pytest.skip(f"Could not start Kafka broker container: {e.stderr}")
        return
    except subprocess.TimeoutExpired:
        print("❌ Docker compose command timed out")
        pytest.skip("Docker compose command timed out")
        return

    print("⏳ Waiting for Kafka broker to become healthy (timeout: 60s)...")
    start_time = time.time()
    kafka_ready = False

    while time.time() - start_time < 60:
        if check_kafka_available(bootstrap_servers, timeout_seconds=2.0):
            kafka_ready = True
            elapsed = time.time() - start_time
            print(f"✅ Kafka is ready! (took {elapsed:.1f}s)")
            break
        time.sleep(2)

    if not kafka_ready:
        print("❌ Kafka failed to start within 60s")
        try:
            run_docker_compose_command(["down", "broker"], cwd=project_root)
        except Exception:
            pass
        pytest.skip("Kafka did not become healthy within 60s")
        return

    yield

    print("\n🧹 Stopping Kafka broker container...")
    try:
        result = run_docker_compose_command(["down", "broker"], cwd=project_root)
        print("✅ Kafka stopped")
        if result.stdout:
            print(f"   {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to stop Kafka: {e.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  Docker compose down timed out")


@pytest.fixture(scope="session")
def kafka_available(auto_start_kafka, integration_kafka_config: ConfigDataModel):
    """Check if Kafka is available, skipping tests otherwise."""
    bootstrap_servers = integration_kafka_config.app.get_kafka_config().bootstrap_servers
    is_available = check_kafka_available(bootstrap_servers, timeout_seconds=3.0)

    if not is_available:
        pytest.skip(
            f"Kafka not available at {bootstrap_servers}. "
            "Either:\n"
            "  1. Set AUTO_START_KAFKA=true to auto-start (default)\n"
            "  2. Manually start with: docker compose up -d broker"
        )

    return True
