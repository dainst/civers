#!/usr/bin/env python3
"""Manual E2E Workflow Testing Script for CiVers Orchestrator.

This script allows manual testing of the complete orchestrator workflow
by publishing test requests and monitoring workflow completion.

Usage:
    # Test with default Arachne test URL
    uv run python scripts/test_workflow.py

    # Test with specific URL
    uv run python scripts/test_workflow.py --url https://arachne.test.dainst.org/entity/12345

    # Test with specific workflow
    uv run python scripts/test_workflow.py --url https://example.com --workflow standard_archive_workflow

    # Specify custom Kafka broker and timeout
    uv run python scripts/test_workflow.py --kafka-broker localhost:29092 --timeout 900
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from transport_services.kafka.event_models import (
    OrchestratorRequestEvent,
    OrchestratorCompletedEvent,
    OrchestratorFailedEvent,
    OrchestratorStatusEvent,
)
from configs.logging_config import setup_logging, get_logger

# Logger will be initialized after setup_logging is called
logger = None

# How often to print a "still waiting" heartbeat (seconds)
PROGRESS_INTERVAL = 30


class WorkflowTester:
    """End-to-end workflow tester for CiVers orchestrator."""

    def __init__(
        self,
        kafka_broker: str = "localhost:29092",
        timeout: int = 300,
    ):
        """Initialize workflow tester.

        Args:
            kafka_broker: Kafka bootstrap server address
            timeout: Maximum time to wait for workflow completion (seconds)
        """
        self.kafka_broker = kafka_broker
        self.timeout = timeout
        self.producer: Optional[KafkaProducer] = None
        self.consumer: Optional[KafkaConsumer] = None

    def start(self):
        """Start Kafka producer and consumer.

        The consumer is created here (before the request is published) so that
        auto_offset_reset="latest" is safe — any response published after this
        point will be received.
        """
        logger.info(f"Connecting to Kafka broker: {self.kafka_broker}")

        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
        )
        logger.info("✅ Kafka producer connected")

        # Consumer uses "latest" because it is created BEFORE the request is
        # submitted (see start() → sleep → submit order in main).  "earliest"
        # would cause the consumer to replay every historical message on these
        # topics before reaching the new one, making the script appear idle.
        self.consumer = KafkaConsumer(
            "orchestrator.status",
            "orchestrator.completed",
            "orchestrator.failed",
            bootstrap_servers=self.kafka_broker,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            group_id=f"workflow_tester_{uuid.uuid4().hex[:8]}",
            consumer_timeout_ms=1000,
        )
        logger.info("✅ Kafka consumer connected")
        logger.info("   Subscribed to: orchestrator.status, orchestrator.completed, orchestrator.failed")

    def stop(self):
        """Stop Kafka producer and consumer."""
        if self.producer:
            self.producer.close()
            logger.info("Producer stopped")

        if self.consumer:
            self.consumer.close()
            logger.info("Consumer stopped")

    def submit_workflow_request(
        self,
        url: str,
        workflow_name: Optional[str] = None,
        priority: int = 5,
        metadata: Optional[dict] = None,
    ) -> str:
        """Submit a workflow request to the orchestrator.

        Args:
            url: URL to process
            workflow_name: Optional workflow name (if None, inferred from domain)
            priority: Processing priority (1-10)
            metadata: Optional metadata dictionary

        Returns:
            request_id: Unique identifier for this request
        """
        request_id = f"test-{uuid.uuid4().hex[:12]}"

        event = OrchestratorRequestEvent(
            request_id=request_id,
            url=url,
            workflow_name=workflow_name,
            priority=priority,
            metadata=metadata or {},
        )

        logger.info("=" * 80)
        logger.info("📤 SUBMITTING WORKFLOW REQUEST")
        logger.info("=" * 80)
        logger.info(f"   Request ID: {request_id}")
        logger.info(f"   URL: {url}")
        logger.info(f"   Workflow: {workflow_name or 'auto-detect from domain'}")
        logger.info(f"   Priority: {priority}")
        logger.info(f"   Metadata: {metadata}")
        logger.info("=" * 80)

        future = self.producer.send(
            topic="orchestrator.requests",
            key=request_id.encode("utf-8"),
            value=event.model_dump(),
        )
        future.get(timeout=10)
        self.producer.flush()

        logger.info("✅ Request published to orchestrator.requests")
        logger.info("")

        return request_id

    def monitor_workflow(self, request_id: str) -> dict:
        """Monitor workflow execution and wait for completion.

        Args:
            request_id: Request ID to monitor

        Returns:
            dict with status, final_event, and execution details

        Raises:
            TimeoutError: If workflow doesn't complete within timeout
        """
        logger.info("=" * 80)
        logger.info("👀 MONITORING WORKFLOW EXECUTION")
        logger.info("=" * 80)
        logger.info(f"   Request ID: {request_id}")
        logger.info(f"   Timeout: {self.timeout} seconds")
        logger.info("=" * 80)
        logger.info("")

        start_time = time.time()
        last_progress_log = start_time
        status_updates = []

        try:
            while True:
                elapsed = time.time() - start_time

                if elapsed > self.timeout:
                    raise TimeoutError(
                        f"Workflow did not complete within {self.timeout} seconds"
                    )

                # Periodic heartbeat so the user knows the script is alive
                if time.time() - last_progress_log >= PROGRESS_INTERVAL:
                    logger.info(f"⏳ Still waiting... ({elapsed:.0f}s elapsed, timeout: {self.timeout}s)")
                    last_progress_log = time.time()

                message_batch = self.consumer.poll(timeout_ms=1000)

                for tp, messages in message_batch.items():
                    for message in messages:
                        topic = message.topic
                        event_data = message.value

                        if event_data.get("request_id") != request_id:
                            continue

                        if topic == "orchestrator.status":
                            event = OrchestratorStatusEvent(**event_data)
                            status_updates.append(event)
                            logger.info("📊 STATUS UPDATE:")
                            logger.info(f"   Step: {event.current_step}")
                            logger.info(f"   Status: {event.status}")
                            if event.message:
                                logger.info(f"   Message: {event.message}")
                            logger.info("")
                            last_progress_log = time.time()  # reset heartbeat on real activity

                        elif topic == "orchestrator.completed":
                            event = OrchestratorCompletedEvent(**event_data)
                            elapsed_time = time.time() - start_time

                            logger.info("=" * 80)
                            logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
                            logger.info("=" * 80)
                            logger.info(f"   Request ID: {request_id}")
                            logger.info(f"   Workflow: {event.workflow_name}")
                            logger.info(f"   Processing Time: {event.processing_time_seconds:.2f}s")
                            logger.info(f"   Total E2E Time: {elapsed_time:.2f}s")
                            logger.info(f"   Status Updates Received: {len(status_updates)}")
                            logger.info("")
                            logger.info("📊 STEP RESULTS:")
                            for key, value in event.step_results.items():
                                logger.info(f"   {key}: {value}")
                            logger.info("=" * 80)

                            return {
                                "status": "completed",
                                "event": event,
                                "status_updates": status_updates,
                                "elapsed_time": elapsed_time,
                            }

                        elif topic == "orchestrator.failed":
                            event = OrchestratorFailedEvent(**event_data)
                            elapsed_time = time.time() - start_time

                            logger.error("=" * 80)
                            logger.error("❌ WORKFLOW FAILED")
                            logger.error("=" * 80)
                            logger.error(f"   Request ID: {request_id}")
                            logger.error(f"   Workflow: {event.workflow_name}")
                            logger.error(f"   Failed Step: {event.failed_step}")
                            logger.error(f"   Error: {event.error_message}")
                            logger.error(f"   Total E2E Time: {elapsed_time:.2f}s")
                            logger.error(f"   Status Updates Received: {len(status_updates)}")
                            if event.error_details:
                                logger.error("")
                                logger.error("📊 ERROR DETAILS:")
                                for key, value in event.error_details.items():
                                    logger.error(f"   {key}: {value}")
                            logger.error("=" * 80)

                            return {
                                "status": "failed",
                                "event": event,
                                "status_updates": status_updates,
                                "elapsed_time": elapsed_time,
                            }

        except TimeoutError:
            logger.error("=" * 80)
            logger.error("⏰ WORKFLOW TIMEOUT")
            logger.error("=" * 80)
            logger.error(f"   Request ID: {request_id}")
            logger.error(f"   Timeout: {self.timeout}s")
            logger.error(f"   Status Updates Received: {len(status_updates)}")
            logger.error("=" * 80)
            raise


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="E2E Workflow Testing Script for CiVers Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with default URL
  uv run python scripts/test_workflow.py

  # Test with specific URL
  uv run python scripts/test_workflow.py --url https://arachne.dainst.org/entity/12345

  # Test with specific workflow
  uv run python scripts/test_workflow.py --url https://example.com --workflow standard_archive_workflow

  # Custom Kafka broker and timeout
  uv run python scripts/test_workflow.py --kafka-broker localhost:29092 --timeout 600
        """,
    )

    parser.add_argument(
        "--url",
        type=str,
        default="https://arachne.test.dainst.org/entity/2003166?fl=20&q=*&resultIndex=2",
        help="URL to process (default: Arachne test URL)",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default=None,
        help="Workflow name to execute (default: auto-detect from domain)",
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=5,
        choices=range(1, 11),
        metavar="[1-10]",
        help="Processing priority (1=low, 10=high, default: 5)",
    )
    parser.add_argument(
        "--kafka-broker",
        type=str,
        default="localhost:29092",
        help="Kafka bootstrap server (default: localhost:29092)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds to wait for workflow completion (default: 600)",
    )
    parser.add_argument(
        "--metadata",
        type=json.loads,
        default=None,
        help='Optional metadata as JSON string (e.g., \'{"key": "value"}\')',
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    global logger
    args = parse_args()

    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("CiVers Orchestrator - E2E Workflow Test")
    logger.info("=" * 80)
    logger.info("")

    tester = WorkflowTester(
        kafka_broker=args.kafka_broker,
        timeout=args.timeout,
    )

    try:
        # Start consumer BEFORE submitting so we don't miss fast responses
        tester.start()
        time.sleep(2)  # Allow consumer to finish partition assignment

        request_id = tester.submit_workflow_request(
            url=args.url,
            workflow_name=args.workflow,
            priority=args.priority,
            metadata=args.metadata,
        )

        result = tester.monitor_workflow(request_id)

        if result["status"] == "completed":
            logger.info("")
            logger.info("✅ E2E test PASSED!")
            sys.exit(0)
        else:
            logger.error("")
            logger.error("❌ E2E test FAILED")
            sys.exit(1)

    except TimeoutError as e:
        logger.error("")
        logger.error(f"❌ E2E test TIMEOUT: {e}")
        sys.exit(2)

    except KafkaError as e:
        logger.error("")
        logger.error(f"❌ Kafka error: {e}")
        logger.error("   Is the Kafka broker running? Check --kafka-broker address.")
        sys.exit(3)

    except Exception as e:
        logger.error("")
        logger.error(f"❌ E2E test ERROR: {e}")
        logger.exception("Stack trace:")
        sys.exit(3)

    finally:
        tester.stop()


if __name__ == "__main__":
    main()
