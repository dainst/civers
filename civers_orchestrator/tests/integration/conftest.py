# tests/integration/conftest.py
"""Pytest fixtures for integration tests.

These fixtures set up real Kafka infrastructure for end-to-end testing.
Tests will be skipped automatically if Kafka is not available.
"""
import asyncio
import os
import socket
import subprocess
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel

# Timeout configuration for Kafka connections (in milliseconds)
KAFKA_CONNECTION_TIMEOUT_MS = 5000  # 5 seconds
KAFKA_REQUEST_TIMEOUT_MS = 10000    # 10 seconds

# Kafka startup configuration
KAFKA_STARTUP_TIMEOUT = 60  # Maximum seconds to wait for Kafka to start
KAFKA_HEALTH_CHECK_INTERVAL = 2  # Seconds between health checks


def run_docker_compose_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a docker compose command.

    Args:
        command: Docker compose command as list (e.g., ["up", "-d", "kafka"])
        cwd: Working directory (project root)

    Returns:
        CompletedProcess with command result

    Raises:
        subprocess.CalledProcessError: If command fails
        FileNotFoundError: If docker compose is not available
    """
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
    """Check if Kafka is available and ready to accept connections.

    This performs both a socket check AND a Kafka client API version check
    to ensure Kafka is fully initialized and ready for use.

    Args:
        bootstrap_servers: Kafka bootstrap servers string (e.g., "localhost:29092")
        timeout_seconds: Maximum time to wait for connection

    Returns:
        True if Kafka is fully ready, False otherwise
    """
    try:
        # First, check if the port is open (faster than Kafka client check)
        host, port = bootstrap_servers.split(":")[0], int(bootstrap_servers.split(":")[1])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_seconds)
        result = sock.connect_ex((host, port))
        sock.close()

        if result != 0:
            return False

        # Port is open - now check if Kafka broker is actually ready
        # This will fail if Kafka is still initializing
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="health-check",
            request_timeout_ms=int(timeout_seconds * 1000),
            api_version_auto_timeout_ms=int(timeout_seconds * 1000),
        )

        # If we can create the client and list topics, Kafka is ready
        admin_client.list_topics()
        admin_client.close()
        return True

    except Exception:
        return False


@pytest.fixture(scope="session")
def auto_start_kafka(integration_kafka_config: ConfigDataModel):
    """Automatically start Kafka via docker compose for integration tests.

    This fixture will:
    1. Start Kafka container using docker compose
    2. Wait for Kafka to become healthy
    3. Yield to tests
    4. Stop Kafka after all tests complete

    Environment variables:
    - AUTO_START_KAFKA: Set to "false" to disable auto-start (default: "true")
    - KAFKA_STARTUP_TIMEOUT: Max seconds to wait for Kafka (default: 60)

    Usage:
        @pytest.mark.usefixtures("auto_start_kafka")
        def test_with_kafka():
            # Kafka is automatically available
            pass

    Note: If Docker is not available or startup fails, tests will be skipped.
    """
    # Check if auto-start is enabled
    auto_start = os.getenv("AUTO_START_KAFKA", "true").lower() == "true"
    if not auto_start:
        print("⏭️  AUTO_START_KAFKA=false - Skipping automatic Kafka startup")
        yield
        return

    # Get project root (where docker-compose.yml is located)
    project_root = Path(__file__).parent.parent.parent

    # Check if docker compose is available
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

    # Check if docker-compose.yml exists
    compose_file = project_root / "docker-compose.yml"
    if not compose_file.exists():
        pytest.skip(f"docker-compose.yml not found at {compose_file}")
        return

    bootstrap_servers = integration_kafka_config.transport.kafka.bootstrap_servers
    print("\n🚀 Starting Kafka container via docker compose...")
    print(f"   Bootstrap servers: {bootstrap_servers}")

    # Start Kafka container
    try:
        result = run_docker_compose_command(["up", "-d", "kafka"], cwd=project_root)
        print("✅ Docker compose up completed")
        if result.stdout:
            print(f"   {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Kafka: {e.stderr}")
        pytest.skip(f"Could not start Kafka container: {e.stderr}")
        return
    except subprocess.TimeoutExpired:
        print("❌ Docker compose command timed out")
        pytest.skip("Docker compose command timed out")
        return

    # Wait for Kafka to become healthy
    print(f"⏳ Waiting for Kafka to become healthy (timeout: {KAFKA_STARTUP_TIMEOUT}s)...")
    start_time = time.time()
    kafka_ready = False

    while time.time() - start_time < KAFKA_STARTUP_TIMEOUT:
        if check_kafka_available(bootstrap_servers, timeout_seconds=2.0):
            kafka_ready = True
            elapsed = time.time() - start_time
            print(f"✅ Kafka is ready! (took {elapsed:.1f}s)")
            break

        time.sleep(KAFKA_HEALTH_CHECK_INTERVAL)

    if not kafka_ready:
        # Kafka didn't start in time - clean up and skip
        print(f"❌ Kafka failed to start within {KAFKA_STARTUP_TIMEOUT}s")
        try:
            run_docker_compose_command(["down", "kafka"], cwd=project_root)
        except Exception:
            pass
        pytest.skip(f"Kafka did not become healthy within {KAFKA_STARTUP_TIMEOUT}s")
        return

    # Kafka is ready - yield to tests
    yield

    # Teardown: Stop Kafka after all tests
    print("\n🧹 Stopping Kafka container...")
    try:
        result = run_docker_compose_command(["down", "kafka"], cwd=project_root)
        print("✅ Kafka stopped")
        if result.stdout:
            print(f"   {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to stop Kafka: {e.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  Docker compose down timed out")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def integration_kafka_config() -> ConfigDataModel:
    """Load configuration from testing.yaml for integration tests.

    Replaces hardcoded configuration with config loaded from:
    - configs/data/environments/testing.yaml (test-specific settings)
    - configs/data/defaults/ (base configuration)

    Uses test_config fixture from tests/conftest.py under the hood.
    """
    config_loader = YamlFileConfigLoader()
    return config_loader.load()


@pytest.fixture(scope="session")
def kafka_available(auto_start_kafka, integration_kafka_config: ConfigDataModel):
    """Check if Kafka is available and skip tests if not.

    This fixture depends on auto_start_kafka which automatically starts Kafka
    if AUTO_START_KAFKA=true (default). If auto-start is disabled or fails,
    it checks if Kafka is already running and skips tests if not.

    This fixture should be used by all integration tests that require Kafka.
    """
    bootstrap_servers = integration_kafka_config.transport.kafka.bootstrap_servers
    is_available = check_kafka_available(bootstrap_servers, timeout_seconds=3.0)

    if not is_available:
        pytest.skip(
            f"Kafka not available at {bootstrap_servers}. "
            "Either:\n"
            "  1. Set AUTO_START_KAFKA=true to auto-start (default)\n"
            "  2. Manually start with: docker compose up -d kafka"
        )

    return True


@pytest.fixture(scope="session")
def kafka_admin_client(integration_kafka_config: ConfigDataModel, kafka_available):
    """Create Kafka admin client for setup/teardown.
    
    This fixture depends on kafka_available to ensure Kafka is running
    before attempting to create the admin client.
    """
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=integration_kafka_config.transport.kafka.bootstrap_servers,
            client_id="integration-test-admin",
            request_timeout_ms=KAFKA_REQUEST_TIMEOUT_MS,
            api_version_auto_timeout_ms=KAFKA_CONNECTION_TIMEOUT_MS,
        )

        yield admin_client

        admin_client.close()
    except NoBrokersAvailable:
        pytest.skip("Kafka brokers not available. Skipping integration tests.")


@pytest.fixture(scope="session")
def setup_kafka_topics(kafka_admin_client, integration_kafka_config):
    """Create Kafka topics for integration tests."""
    topics = integration_kafka_config.transport.kafka.topics

    topic_names = [
        topics.orchestrator_requests,
        topics.orchestrator_status,
        topics.orchestrator_completed,
        topics.orchestrator_failed,
    ]

    # Create topics
    new_topics = [
        NewTopic(name=topic, num_partitions=1, replication_factor=1)
        for topic in topic_names
    ]

    try:
        kafka_admin_client.create_topics(new_topics, validate_only=False)
        print(f"✅ Created Kafka topics: {topic_names}")
    except TopicAlreadyExistsError:
        print(f"ℹ️ Kafka topics already exist: {topic_names}")

    # Wait for topics to be ready
    time.sleep(2)

    yield

    # Cleanup: Delete topics after tests
    try:
        kafka_admin_client.delete_topics(topic_names)
        print(f"🧹 Deleted Kafka topics: {topic_names}")
    except Exception as e:
        print(f"⚠️ Could not delete topics: {e}")


@pytest_asyncio.fixture
async def mock_orchestrator_service():
    """Create a mock orchestrator service for testing."""
    from unittest.mock import Mock

    from configs.models import WorkflowStepConfig
    from models.orchestrator_models import StepInstruction

    mock_service = Mock()

    # Create mock step config
    mock_step_config = Mock(spec=WorkflowStepConfig)
    mock_step_config.name = "archive_generation"
    mock_step_config.component = "archive_generator"

    # Create mock instruction
    mock_instruction = Mock(spec=StepInstruction)
    mock_instruction.step_config = mock_step_config
    mock_instruction.request_id = "test-123"
    mock_instruction.component = "archive_generator"
    mock_instruction.input_schema = "ArchiveRequest"
    mock_instruction.input_data = {}
    mock_instruction.url = "https://example.com"

    # Mock start_workflow to return instruction
    mock_service.start_workflow = Mock(return_value=mock_instruction)
    mock_service.step_completed = Mock()
    mock_service.step_failed = Mock()

    return mock_service


@pytest_asyncio.fixture
async def kafka_transport_service(
    integration_kafka_config: ConfigDataModel,
    mock_orchestrator_service,
    kafka_available  # Ensure Kafka is available before creating service
) -> AsyncGenerator:
    """Create KafkaTransportService for integration testing.
    
    This fixture depends on kafka_available to ensure Kafka is running
    before attempting to create the transport service.
    """
    from transport_services.kafka.kafka_transport_service import KafkaTransportService

    service = KafkaTransportService(integration_kafka_config, mock_orchestrator_service)

    yield service

    # Cleanup
    await service.stop()

