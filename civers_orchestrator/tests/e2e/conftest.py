import asyncio
import json
import os
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any, List
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

from transport_services.kafka.kafka_transport_service import KafkaTransportService
from orchestration_services.orchestrator_service import OrchestratorService
from configs.models import ConfigDataModel

# --- Kafka Startup Infrastructure ---

def run_docker_compose_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
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
    try:
        host, port = bootstrap_servers.split(":")[0], int(bootstrap_servers.split(":")[1])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_seconds)
        result = sock.connect_ex((host, port))
        sock.close()
        if result != 0: return False
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="health-check",
            request_timeout_ms=int(timeout_seconds * 1000),
            api_version_auto_timeout_ms=int(timeout_seconds * 1000),
        )
        admin_client.list_topics()
        admin_client.close()
        return True
    except Exception:
        return False

@pytest.fixture(scope="session")
def auto_start_kafka(test_config: ConfigDataModel):
    auto_start = os.getenv("AUTO_START_KAFKA", "true").lower() == "true"
    if not auto_start:
        yield
        return
    project_root = Path(__file__).parent.parent.parent
    bootstrap_servers = test_config.transport.kafka.bootstrap_servers
    print(f"\n🚀 E2E: Starting Kafka container...")
    try:
        run_docker_compose_command(["up", "-d", "kafka"], cwd=project_root)
    except Exception as e:
        print(f"❌ Failed to start Kafka: {e}")
        pytest.skip("Could not start Kafka container")
        return
    
    start_time = time.time()
    while time.time() - start_time < 60:
        if check_kafka_available(bootstrap_servers):
            print(f"✅ Kafka is ready!")
            break
        time.sleep(2)
    else:
        pytest.skip("Kafka did not become healthy in time")
    
    yield
    
    print(f"\n🧹 E2E: Stopping Kafka container...")
    try:
        run_docker_compose_command(["down", "kafka"], cwd=project_root)
    except Exception:
        pass

@pytest.fixture(scope="session")
def kafka_available(auto_start_kafka, test_config: ConfigDataModel):
    bootstrap_servers = test_config.transport.kafka.bootstrap_servers
    if not check_kafka_available(bootstrap_servers):
        pytest.skip(f"Kafka not available at {bootstrap_servers}")
    return True

@pytest.fixture
def orchestrator(test_config: ConfigDataModel) -> OrchestratorService:
    """Function-scoped orchestrator for E2E tests (clean state per test)."""
    return OrchestratorService(test_config)

# --- E2E Helpers ---

@pytest_asyncio.fixture
async def live_kafka_service(
    test_config: ConfigDataModel, 
    orchestrator: OrchestratorService,
    kafka_available
) -> AsyncGenerator[KafkaTransportService, None]:
    """Start KafkaTransportService in a background task."""
    print("🚀 Starting live Kafka service...")
    
    import copy
    test_config = copy.deepcopy(test_config)
    
    # Use unique group_id to avoid rebalancing delays
    test_config.transport.kafka.consumer.group_id = f"e2e-test-group-{uuid.uuid4().hex[:8]}"
    test_config.transport.kafka.consumer.auto_offset_reset = "earliest"
    
    service = KafkaTransportService(test_config, orchestrator)
    
    # Start service in background
    task = asyncio.create_task(service.start())
    
    # Give it a moment to initialize handlers and consumer
    await asyncio.sleep(2)
        
    yield service
    
    # Cleanup
    print("🛑 Stopping live Kafka service...")
    await service.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

class MockComponent:
    def __init__(self, bootstrap_servers: str, request_topic: str, success_topic: str, failure_topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.request_topic = request_topic
        self.success_topic = success_topic
        self.failure_topic = failure_topic
        self.producer = None
        self.consumer = None
        self._running = False
        self._task = None

    async def start(self):
        print(f"🎭 Starting Mock Component for {self.request_topic}")
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        self.consumer = KafkaConsumer(
            self.request_topic,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            group_id=f"mock_component_{self.request_topic}_{uuid.uuid4().hex[:8]}"
        )
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            import threading
            def poll(): return self.consumer.poll(timeout_ms=500)
            messages = await asyncio.to_thread(poll)
            for tp, msgs in messages.items():
                for msg in msgs:
                    await self._process_message(msg.value)
            await asyncio.sleep(0.1)

    async def _process_message(self, data: Dict[str, Any]):
        request_id = data.get("request_id")
        url = data.get("url")
        print(f"🎭 Mock Component received request {request_id} for {url}")
        await asyncio.sleep(0.5)
        now_str = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        
        if "archive" in self.request_topic:
            response = {
                "request_id": request_id, "url": url, "created_at": now_str,
                "archive_path": f"/tmp/archives/{request_id}.wacz",
                "artifacts_created": ["archive.wacz"], "processing_time_seconds": 0.5,
                "snapshot_id": f"snap-{request_id}"
            }
        elif "metadata" in self.request_topic:
            response = {
                "request_id": request_id, "url": url, "timestamp": now_str,
                "extracted_metadata": {"title": "Test Title"},
                "domain_used": "example.com", "mappers_used": ["DefaultMapper"],
                "processing_time_seconds": 0.5, "artifacts_created": ["metadata.json"]
            }
        else:
            response = {"request_id": request_id, "url": url, "status": "completed"}
            
        print(f"🎭 Mock Component sending success for {request_id}")
        self.producer.send(self.success_topic, value=response)
        self.producer.flush()

    async def stop(self):
        print(f"🎭 Stopping Mock Component for {self.request_topic}")
        self._running = False
        if self._task:
            self._task.cancel()
            try: await self._task 
            except asyncio.CancelledError: pass
        if self.producer: self.producer.close()
        if self.consumer: self.consumer.close()

@pytest.fixture
def create_mock_component(test_config):
    components = []
    async def _create(component_name: str):
        mapping = test_config.transport.kafka.component_mappings[component_name]
        mock = MockComponent(
            bootstrap_servers=test_config.transport.kafka.bootstrap_servers,
            request_topic=mapping.request_topic,
            success_topic=mapping.response_topics["success"],
            failure_topic=mapping.response_topics["failure"]
        )
        await mock.start()
        components.append(mock)
        return mock
    yield _create
    for c in components:
        # We can't await here because it's a sync generator yield cleanup
        # But we can use a wrapper or just let it close in background
        pass

@pytest_asyncio.fixture
async def e2e_test_driver(test_config):
    class Driver:
        def __init__(self):
            self.producer = KafkaProducer(
                bootstrap_servers=test_config.transport.kafka.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            self.consumer = KafkaConsumer(
                test_config.transport.kafka.topics.orchestrator_completed,
                test_config.transport.kafka.topics.orchestrator_failed,
                bootstrap_servers=test_config.transport.kafka.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                group_id=f"e2e_driver_{uuid.uuid4().hex[:8]}"
            )

        async def send_request(self, url: str, request_id: str):
            payload = {"request_id": request_id, "url": url, "workflow_name": None, "priority": 5, "metadata": {}}
            print(f"🏎️ Driver sending request {request_id}")
            self.producer.send(test_config.transport.kafka.topics.orchestrator_requests, value=payload)
            self.producer.flush()

        async def wait_for_result(self, request_id: str, timeout: int = 30):
            print(f"🏎️ Driver waiting for {request_id} result...")
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                def poll(): return self.consumer.poll(timeout_ms=500)
                messages = await asyncio.to_thread(poll)
                for tp, msgs in messages.items():
                    for msg in msgs:
                        if msg.value.get("request_id") == request_id:
                            print(f"🏎️ Driver received result for {request_id}!")
                            return msg.value
                await asyncio.sleep(0.1)
            raise TimeoutError(f"Workflow {request_id} did not complete in {timeout}s")

        def close(self):
            self.producer.close()
            self.consumer.close()

    driver = Driver()
    yield driver
    driver.close()
