"""
Unified Docker container management for integration tests.
All integration tests should use these shared fixtures.
"""
import os
import subprocess
import time
import socket
import pytest
from pathlib import Path
from typing import List, Optional

# Test configuration
TEST_DIR = Path(__file__).parent.parent
PROJECT_ROOT = TEST_DIR.parent
MAIN_DOCKER_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
TEST_DOCKER_COMPOSE = TEST_DIR / "test-docker-compose.yml"


def _run_cmd(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd, 
        cwd=cwd or PROJECT_ROOT, 
        capture_output=True, 
        text=True, 
        check=check
    )


def _wait_for_port(host: str, port: int, timeout: float = 60.0) -> bool:
    """Wait for a port to become available."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def _create_kafka_topics(compose_file: Path, service_name: str, bootstrap_server: str):
    """Create required Kafka topics."""
    topics = [
        ("archive.requests", 3),
        ("archive.status", 3),
        ("archive.completed", 3),
        ("archive.failed", 3),
    ]
    
    for topic_name, partitions in topics:
        cmd = [
            "docker", "compose", "-f", str(compose_file), "exec", "-T", service_name,
            "bash", "-lc",
            f"/opt/kafka/bin/kafka-topics.sh --bootstrap-server {bootstrap_server} --create --if-not-exists --topic {topic_name} --partitions {partitions} --replication-factor 1"
        ]
        result = _run_cmd(cmd, check=False)
        print(f"Topic {topic_name}: {result.stdout.strip()}")


@pytest.fixture(scope="session")
def test_kafka_only():
    """
    Start only test Kafka broker (lightweight, fast).
    Use this for tests that only need Kafka functionality.
    """
    print("🐳 Starting test Kafka container...")
    
    # Start test broker
    _run_cmd(["docker", "compose", "-f", str(TEST_DOCKER_COMPOSE), "up", "-d", "test-broker"])
    
    # Wait for Kafka
    if not _wait_for_port("localhost", 29093, timeout=60):
        pytest.fail("❌ Test Kafka broker not ready")
    
    # Create topics
    _create_kafka_topics(TEST_DOCKER_COMPOSE, "test-broker", "localhost:9092")
    
    print("✅ Test Kafka ready")
    yield
    
    # Cleanup
    print("🧹 Cleaning up test Kafka...")
    _run_cmd(["docker", "compose", "-f", str(TEST_DOCKER_COMPOSE), "down", "-v"], check=False)


@pytest.fixture(scope="session")
def test_full_stack():
    """
    Start complete test stack (test Kafka + test archive generator).
    Use this for full end-to-end integration tests with isolated test environment.
    """
    print("🐳 Starting complete test stack...")
    
    # Check if containers are already running
    check_cmd = ["docker", "compose", "-f", str(TEST_DOCKER_COMPOSE), "ps", "-q"]
    result = _run_cmd(check_cmd, check=False)
    
    if result.stdout.strip():
        print("♻️ Some test containers already running, ensuring full test stack...")
    
    # Start all test services (broker + archive-generator)
    _run_cmd(["docker", "compose", "-f", str(TEST_DOCKER_COMPOSE), "up", "-d", "test-broker", "test-archive-generator"])
    
    # Wait for Kafka
    if not _wait_for_port("localhost", 29093, timeout=60):
        pytest.fail("❌ Test Kafka broker not ready")
    
    # Create topics
    _create_kafka_topics(TEST_DOCKER_COMPOSE, "test-broker", "localhost:9092")
    
    # Wait a bit for archive generator to be ready
    time.sleep(10)
    
    print("✅ Complete test stack ready")
    yield
    
    # Cleanup
    print("🧹 Cleaning up complete test stack...")
    _run_cmd(["docker", "compose", "-f", str(TEST_DOCKER_COMPOSE), "down", "-v"], check=False)


@pytest.fixture(scope="session") 
def main_kafka_only():
    """
    Start only main Kafka broker (production-like).
    Use this for tests that need production Kafka setup.
    """
    print("🐳 Starting main Kafka container...")
    
    # Check if full stack is already running
    check_cmd = ["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "ps", "-q", "broker"]
    result = _run_cmd(check_cmd, check=False)
    
    if result.stdout.strip():
        print("♻️ Reusing existing Kafka broker from full stack")
        # Just ensure topics exist
        _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
        print("✅ Main Kafka ready (reused)")
        yield
        # Don't cleanup - let full_stack handle it
        return
    
    # Start main broker if not running
    _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "up", "-d", "broker"])
    
    # Wait for Kafka
    if not _wait_for_port("localhost", 29092, timeout=60):
        pytest.fail("❌ Main Kafka broker not ready")
    
    # Create topics
    _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
    
    print("✅ Main Kafka ready")
    yield
    
    # Only cleanup if we started it (not if full_stack is running)
    check_cmd = ["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "ps", "-q", "archive-generator"]
    result = _run_cmd(check_cmd, check=False)
    
    if not result.stdout.strip():
        print("🧹 Cleaning up main Kafka...")
        _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "down", "-v"], check=False)
    else:
        print("🔄 Keeping Kafka running (full stack active)")


@pytest.fixture(scope="session")
def full_stack():
    """
    Start full application stack (Kafka + UI + Archive Generator).
    Use this for end-to-end integration tests.
    """
    print("🐳 Starting full application stack...")
    
    # Check if containers are already running
    check_cmd = ["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "ps", "-q"]
    result = _run_cmd(check_cmd, check=False)
    
    if result.stdout.strip():
        print("♻️ Some containers already running, ensuring full stack...")
        # Start any missing services
        _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "up", "-d", "broker", "kafka-ui", "archive-generator"])
    else:
        # Skip rebuild if requested
        skip_build = os.environ.get("SKIP_BUILD", "false").lower() == "true"
        
        if not skip_build:
            print("🔨 Building archive-generator...")
            _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "build", "archive-generator"])
        else:
            print("⏭️ Skipping build (SKIP_BUILD=true)")
        
        # Start all services
        _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "up", "-d", "broker", "kafka-ui", "archive-generator"])
    
    # Wait for services
    print("⏳ Waiting for services...")
    if not _wait_for_port("localhost", 29092, timeout=60):
        pytest.fail("❌ Kafka not ready")
    if not _wait_for_port("localhost", 8089, timeout=30):
        pytest.fail("❌ Kafka UI not ready") 
    
    # Create topics
    _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
    
    print("✅ Full stack ready")
    yield
    
    # Cleanup
    print("🧹 Cleaning up full stack...")
    _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "down", "-v"], check=False)


@pytest.fixture(scope="session")
def smart_kafka():
    """
    Intelligent Kafka fixture that starts the minimum required setup.
    Reuses containers when possible to avoid long startup times.
    """
    print("🧠 Smart Kafka: Analyzing container state...")
    
    # Check what's already running
    check_full_cmd = ["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "ps", "-q"]
    result = _run_cmd(check_full_cmd, check=False)
    running_containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    if len(running_containers) >= 2:  # Multiple containers running
        print("♻️ Full stack detected, reusing existing containers")
        _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
        print("✅ Smart Kafka ready (reused full stack)")
        yield "full_stack"
        # Don't cleanup - let full stack manage lifecycle
        return
    
    # Check if just broker is running
    check_broker_cmd = ["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "ps", "-q", "broker"]
    result = _run_cmd(check_broker_cmd, check=False)
    
    if result.stdout.strip():
        print("♻️ Kafka broker detected, reusing existing container")
        _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
        print("✅ Smart Kafka ready (reused broker)")
        yield "kafka_only"
        # Don't cleanup - let caller manage lifecycle
        return
    
    # Nothing running, start minimal Kafka
    print("🐳 Starting minimal Kafka setup...")
    _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "up", "-d", "broker"])
    
    if not _wait_for_port("localhost", 29092, timeout=60):
        pytest.fail("❌ Kafka broker not ready")
    
    _create_kafka_topics(MAIN_DOCKER_COMPOSE, "broker", "localhost:9092")
    print("✅ Smart Kafka ready (new broker)")
    
    yield "kafka_only"
    
    # Only cleanup if we started it fresh
    print("🧹 Cleaning up smart Kafka...")
    _run_cmd(["docker", "compose", "-f", str(MAIN_DOCKER_COMPOSE), "down"], check=False)


@pytest.fixture(scope="function")
def reuse_containers():
    """
    Check if containers are already running and reuse them.
    Use this for development when you want to keep containers running.
    """
    # This fixture doesn't start anything, just signals that containers should be reused
    yield
    # No cleanup - containers keep running


# Convenience fixtures for common patterns
@pytest.fixture(scope="session")
def kafka_for_development(reuse_containers, main_kafka_only):
    """Try to reuse containers, fallback to starting main Kafka."""
    yield


@pytest.fixture(scope="session") 
def kafka_for_ci():
    """Always start fresh test Kafka for CI environments."""
    with test_kafka_only():
        yield


# Fixture selection helper
def get_docker_fixture():
    """
    Helper to choose the right Docker fixture based on environment.
    
    Environment variables:
    - TEST_MODE=fast -> test_kafka_only
    - TEST_MODE=full -> full_stack  
    - TEST_MODE=reuse -> reuse_containers
    - Default: test_kafka_only
    """
    mode = os.environ.get("TEST_MODE", "fast").lower()
    
    if mode == "full":
        return "full_stack"
    elif mode == "reuse":
        return "reuse_containers"
    else:
        return "test_kafka_only"
