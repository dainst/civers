# Utility Scripts

This directory contains standalone scripts designed for **active development, manual debugging, and plumbing verification** of the CiVers Orchestrator.

> [!IMPORTANT]
> Unlike the automated E2E tests (`tests/e2e/`), these scripts interact with YOUR live infrastructure. They provide a human-friendly "Live Dashboard" view of Kafka traffic.

## test_workflow.py

A manual testing utility that submits a workflow request to Kafka and monitors its entire lifecycle.

### Key Features

1. **Development Dashboard**: Provides real-time visibility into the orchestrator's state transitions via the `orchestrator.status` topic.
2. **Infrastructure Verification**: Proves that the "plumbing" (Kafka connectivity, topic creation, request/response cycle) is working in a real environment.
3. **Pydantic Validation**: Uses exact production models to ensure that events being published/consumed are schema-compliant.
4. **Failure Analysis**: Allows you to monitor how the system handles timeouts or manual worker failures in real-time.

### Environment Requirements

To see a workflow reach **COMPLETED** status, you MUST have:

1. A running **Kafka** container.
2. A running **Orchestrator** service.
3. **External Workers** (e.g., Archive Generator, Metadata Extractor) listening to their respective topics and sending response events.

*Note: If no workers are running, the script will show the first step as `in_progress` and eventually report a **TIMEOUT** when the orchestrator's background monitoring task cancels the workflow.*

### Usage

```bash
# Ensure Kafka is running
docker compose up -d kafka

# Run the orchestrator in one terminal
uv run python main.py

# Run a test workflow in another terminal
uv run python scripts/test_workflow.py --url https://arachne.test.dainst.org/entity/2003166
```

### Advanced Options

```bash
# Run with a specific workflow and custom timeout
uv run python scripts/test_workflow.py --workflow simple_workflow --timeout 60

# Specify a remote Kafka broker
uv run python scripts/test_workflow.py --kafka-broker 192.168.1.100:9092

# Pass custom metadata
uv run python scripts/test_workflow.py --metadata '{"user_id": "sammar", "priority": 10}'
```

### Expected Output

When the orchestrator and script are both running, you will see real-time updates:

```text
📤 SUBMITTING WORKFLOW REQUEST
--------------------------------------------------------------------------------
Request ID: test-a1b2c3d4
URL: https://arachne.test.dainst.org/entity/2003166
Workflow: auto-detect from domain

👀 MONITORING WORKFLOW EXECUTION
--------------------------------------------------------------------------------
📊 STATUS UPDATE:
   Step: archive_generation
   Status: in_progress

📊 STATUS UPDATE:
   Step: metadata_extraction
   Status: in_progress

✅ WORKFLOW COMPLETED SUCCESSFULLY
--------------------------------------------------------------------------------
   Processing Time: 45.22s
   Total E2E Time: 46.10s
```

### Troubleshooting

- **"Topic orchestrator.status not found"**: This error occurs if the orchestrator hasn't started and created the topics yet. Start the orchestrator first.
- **Script hangs at "archive_generation [in_progress]"**:
  - This is expected if you haven't started your worker components (like the Archive Generator). The script is waiting for a response event that will never come.
  - The orchestrator will eventually time out the request based on its internal monitoring.
- **"ImportError"**: Ensure you run the script with `uv run` to include all project dependencies.
