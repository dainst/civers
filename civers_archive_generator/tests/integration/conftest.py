"""Kafka broker setup, scoped to the integration tests."""

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from configs.models import ConfigDataModel
from kafka import KafkaAdminClient
from kafka.errors import KafkaError

# Kafka service name in the root Compose file.
KAFKA_SERVICE = "kafka"


def run_docker_compose_command(
    command: list[str], cwd: Path
) -> subprocess.CompletedProcess:
    """Run a docker compose command."""
    full_command = ["docker", "compose"] + command
    return subprocess.run(
        full_command, cwd=cwd, capture_output=True, text=True, check=True, timeout=30
    )


def check_kafka_available(bootstrap_servers: str, timeout_seconds: float = 3.0) -> bool:
    """Check if Kafka is available and accepting connections."""
    try:
        host, port = (
            bootstrap_servers.split(":")[0],
            int(bootstrap_servers.split(":")[1]),
        )
        with socket.create_connection((host, port), timeout=timeout_seconds):
            pass

        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="health-check-ag",
            request_timeout_ms=int(timeout_seconds * 1000),
            api_version_auto_timeout_ms=int(timeout_seconds * 1000),
        )

        try:
            admin_client.list_topics()
        finally:
            admin_client.close()
        return True
    except (KafkaError, OSError, ValueError):
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

    # Run Compose from the repository root.
    project_root = Path(__file__).resolve().parents[3]

    bootstrap_servers = integration_kafka_config.transport.get_transport_config(
        "kafka"
    )["bootstrap_servers"]

    # Reuse an available broker and leave it running after the tests.
    if check_kafka_available(bootstrap_servers, timeout_seconds=2.0):
        print(f"\n✅ Kafka already reachable at {bootstrap_servers} — leaving it alone")
        yield
        return

    try:
        subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=True, timeout=5
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        pytest.skip(
            "Docker Compose not available. Install Docker to run integration tests."
        )
        return

    compose_file = project_root / "docker-compose.yml"
    if not compose_file.exists():
        pytest.skip(f"docker-compose.yml not found at {compose_file}")
        return

    print(f"\n🚀 Starting the '{KAFKA_SERVICE}' container via docker compose...")
    print(f"   Bootstrap servers: {bootstrap_servers}")

    try:
        result = run_docker_compose_command(
            ["up", "-d", KAFKA_SERVICE], cwd=project_root
        )
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
            run_docker_compose_command(["stop", KAFKA_SERVICE], cwd=project_root)
        except (subprocess.SubprocessError, OSError) as error:
            print(f"Could not stop Kafka after its startup timeout: {error}")
        pytest.skip("Kafka did not become healthy within 60s")
        return

    yield

    print("\n🧹 Stopping Kafka broker container...")
    try:
        result = run_docker_compose_command(["stop", KAFKA_SERVICE], cwd=project_root)
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
    bootstrap_servers = integration_kafka_config.transport.get_transport_config(
        "kafka"
    )["bootstrap_servers"]
    is_available = check_kafka_available(bootstrap_servers, timeout_seconds=3.0)

    if not is_available:
        pytest.skip(
            f"Kafka not available at {bootstrap_servers}. "
            "Either:\n"
            "  1. Set AUTO_START_KAFKA=true to auto-start (default)\n"
            f"  2. Manually start with: (cd .. && docker compose up -d {KAFKA_SERVICE})"
        )

    return True
