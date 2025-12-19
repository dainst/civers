"""
Consolidated Kafka integration tests.
This file contains all Kafka-related integration tests using the isolated test environment.

Run with: pytest tests/integration/kafka/test_kafka_core.py --run-integration -v
"""
import os
import subprocess
import time
import json
import pytest
from tests.fixtures.docker_fixtures import test_kafka_only

# Use test environment for all Kafka tests
TEST_DIR = os.path.dirname(os.path.dirname(__file__))
TEST_COMPOSE_FILE = os.path.join(TEST_DIR, 'test-docker-compose.yml')

pytestmark = [pytest.mark.integration, pytest.mark.kafka]


def _run_cmd(cmd, timeout=10):
    """Run a command with timeout."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True if isinstance(cmd, str) else False,
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=TEST_DIR
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.skip(f"Command timed out: {cmd}")
    except Exception as e:
        pytest.skip(f"Command failed: {cmd}, error: {e}")


def test_kafka_message_publishing(test_kafka_only):
    """Consolidated test for Kafka message publishing using test environment."""
    request_id = f"kafka-test-{int(time.time() * 1000)}"
    request = {
        "request_id": request_id,
        "url": "https://httpbin.org/get",
        "created_at": "2025-08-11T12:00:00Z",
        "priority": 1
    }
    payload = json.dumps(request)

    # Publish message to test Kafka
    produce_cmd = f"""docker compose -f tests/test-docker-compose.yml exec -T test-broker bash -c "echo '{request_id}\t{payload}' | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic archive.requests --property parse.key=true --property key.separator=\t" """
    
    result = _run_cmd(produce_cmd, timeout=10)
    
    if result.returncode != 0:
        pytest.skip(f"Test Kafka not accessible: {result.stderr}")

    # Verify message was published
    consume_cmd = f"""docker compose -f tests/test-docker-compose.yml exec -T test-broker bash -c "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic archive.requests --from-beginning --timeout-ms 5000 --max-messages 1" """
    
    result = _run_cmd(consume_cmd, timeout=10)
    
    assert request_id in result.stdout, "Message should appear in topic"
    print(f"✅ Kafka message publishing test passed for {request_id}")


def test_kafka_topics_exist(test_kafka_only):
    """Consolidated test for Kafka topics existence."""
    list_cmd = """docker compose -f tests/test-docker-compose.yml exec -T test-broker bash -c "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list" """
    
    result = _run_cmd(list_cmd, timeout=10)
    
    if result.returncode != 0:
        pytest.skip("Cannot access test Kafka topics")
    
    required_topics = ["archive.requests", "archive.status", "archive.completed", "archive.failed"]
    output = result.stdout
    
    for topic in required_topics:
        assert topic in output, f"Topic {topic} should exist"
    
    print("✅ All required Kafka topics exist and are accessible")


def test_kafka_connection_direct():
    """Test direct Kafka connection to test environment."""
    try:
        import socket
        # Test connection to test Kafka on port 29093
        with socket.create_connection(("localhost", 29093), timeout=5):
            print("✅ Direct Kafka connection successful")
    except Exception as e:
        pytest.skip(f"Could not connect to test Kafka on port 29093: {e}")
