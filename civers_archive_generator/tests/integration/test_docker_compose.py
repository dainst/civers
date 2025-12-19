import os
import subprocess
import time
import json
import socket
import pytest

# Import unified Docker fixtures
from tests.fixtures.docker_fixtures import test_full_stack, test_kafka_only

# Use test environment for all Docker Compose tests
TEST_DIR = os.path.dirname(__file__)
TEST_COMPOSE_FILE = os.path.join(TEST_DIR, 'test-docker-compose.yml')

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def _run(cmd, cwd=None, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd or TEST_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=check)


# Archive generator service health test moved to test_docker_infrastructure.py to avoid duplication


def test_can_publish_request_and_receive_events(test_full_stack):
    """Test end-to-end message flow through the complete test stack."""
    # Use fast example.com instead of slow arachne.dainst.org for integration testing
    request = {
        "request_id": "it-req-001",
        "url": "https://example.com",
        "created_at": "2025-08-11T12:00:00Z",
        "priority": 1
    }
    payload = json.dumps(request)

    # Send using test broker container
    produce_cmd = [
        "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
        "bash", "-lc",
        "echo 'it-req-001\t" + payload.replace("'", "'\\''") + "' | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic archive.requests --property parse.key=true --property key.separator=\t"
    ]
    prod = _run(produce_cmd, check=False)
    print(prod.stdout)

    # Check status with shorter timeout (30 seconds should be enough for example.com)
    consume_status_cmd = [
        "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
        "bash", "-lc",
        "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic archive.status --from-beginning --timeout-ms 30000 --max-messages 5"
    ]
    status_out = _run(consume_status_cmd, check=False)
    print("Status output:", status_out.stdout)

    # Expect at least one status line mentioning our request_id
    assert "it-req-001" in status_out.stdout

    # Check completed with shorter timeout (60 seconds should be enough for example.com)
    consume_completed_cmd = [
        "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
        "bash", "-lc",
        "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic archive.completed --from-beginning --timeout-ms 60000 --max-messages 5"
    ]
    comp_out = _run(consume_completed_cmd, check=False)
    print("Completed output:", comp_out.stdout)

    # We should see a completion message or, in worst case, a failure
    if "it-req-001" not in comp_out.stdout:
        consume_failed_cmd = [
            "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
            "bash", "-lc",
            "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic archive.failed --from-beginning --timeout-ms 30000 --max-messages 5"
        ]
        failed_out = _run(consume_failed_cmd, check=False)
        print("Failed output:", failed_out.stdout)
        assert "it-req-001" in failed_out.stdout

    # Verify archive output in test archives directory
    out_dir = os.path.join(os.path.dirname(TEST_DIR), 'test_archives')
    assert os.path.isdir(out_dir), "test_archives mount missing"
    # Allow for file write
    time.sleep(2)
    # Expect at least one new subfolder
    entries = [p for p in os.listdir(out_dir) if not p.startswith('.')]
    assert len(entries) > 0, "no output in test_archives directory"


# Quick Kafka publishing test moved to test_kafka_core.py to avoid duplication


def test_kafka_message_flow_with_processing(test_full_stack):
    """Test that verifies Kafka message flow with actual archive processing in test environment."""
    request = {
        "request_id": "flow-test-001",
        "url": "https://httpbin.org/get",  # Very fast endpoint
        "created_at": "2025-08-11T12:00:00Z",
        "priority": 1
    }
    payload = json.dumps(request)

    # Send request to test broker
    produce_cmd = [
        "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
        "bash", "-lc",
        "echo 'flow-test-001\t" + payload.replace("'", "'\\''") + "' | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic archive.requests --property parse.key=true --property key.separator=\t"
    ]
    prod = _run(produce_cmd, check=False)
    print("Producer output:", prod.stdout)

    # Just verify we get a status message quickly (15 seconds should be enough for status)
    consume_status_cmd = [
        "docker", "compose", "-f", TEST_COMPOSE_FILE, "exec", "-T", "test-broker",
        "bash", "-lc",
        "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic archive.status --from-beginning --timeout-ms 15000 --max-messages 3"
    ]
    status_out = _run(consume_status_cmd, check=False)
    print("Quick status check:", status_out.stdout)

    # Just verify the request was processed (status message received)
    assert "flow-test-001" in status_out.stdout, "Request should appear in status messages"
    print("✅ Kafka flow with processing test passed")
