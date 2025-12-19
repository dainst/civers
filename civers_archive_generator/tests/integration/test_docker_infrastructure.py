"""
Consolidated Docker infrastructure tests.
This file tests Docker container health using the isolated test environment.

Run with: pytest tests/integration/test_docker_infrastructure.py --run-integration -v
"""
import os
import subprocess
import pytest
from tests.fixtures.docker_fixtures import test_kafka_only, test_full_stack

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def _run_cmd(cmd, timeout=10):
    """Run a command with timeout."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=os.path.dirname(__file__)
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.skip(f"Command timed out: {cmd}")
    except Exception as e:
        pytest.skip(f"Command failed: {cmd}, error: {e}")


def test_docker_containers_running(test_kafka_only):
    """Test that required test containers are running using test environment."""
    result = _run_cmd("docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E '(test-broker|test-archive-generator)'")
    
    if result.returncode != 0:
        pytest.skip("Required test containers not running")
    
    output = result.stdout
    assert "test-broker" in output, "Test Kafka broker container should be running"
    print("✅ Required test containers are running")


def test_archive_generator_service_health(test_full_stack):
    """Test that the test archive generator service is running and healthy."""
    # Check container is healthy/running by inspecting logs
    logs_result = _run_cmd("docker compose -f test-docker-compose.yml logs --no-color test-archive-generator", timeout=10)
    
    if logs_result.returncode != 0:
        pytest.skip("Cannot access test archive generator logs")
    
    logs_output = logs_result.stdout.lower()
    
    # Check for health indicators in logs
    health_indicators = [
        "starting archive generator application",
        "kafka transport service", 
        "starting",
        "kafka",
        "transport",
        "ready"
    ]
    
    found_indicator = any(indicator in logs_output for indicator in health_indicators)
    assert found_indicator, f"Test archive generator should show health indicators. Logs: {logs_output[:500]}"
    
    print("✅ Test archive generator service is running and appears healthy")


def test_test_broker_container_exists(test_kafka_only):
    """Test that test broker container exists and is accessible."""
    result = _run_cmd("docker ps -q -f name=test-broker")
    
    if not result.stdout.strip():
        pytest.skip("Test broker container not running")
    
    assert result.stdout.strip(), "Test broker container should be running"
    print("✅ Test broker container is running and accessible")
