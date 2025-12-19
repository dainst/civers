# Models

Data structures for workflow orchestration and runtime state management.

## Overview

This module contains data models for orchestration and workflow execution:

1. **Orchestrator Models** (`orchestrator_models.py`) - Communication between orchestrator and transport layer
2. **Workflow Models** (`workflow_models.py`) - Runtime state tracking for workflow execution

**Key Design Principles:**
- **Separation of Concerns** - Clear boundaries between configuration, orchestration, and runtime state
- **Transport Agnostic** - Orchestrator models don't reference Kafka/transport specifics
- **Stateful Tracking** - Workflow models track execution progress and results
- **Data Passing** - Step results enable dependencies between workflow steps

---

## Quick Overview

### Orchestrator Models (orchestrator_models.py)

Data structures for orchestrator-to-transport communication using **dataclasses**.

| Class | Purpose | Fields |
|-------|---------|--------|
| `StepInstruction` | Transport-agnostic instruction to execute a step | 7 fields |
| `WorkflowTransition` | Result of workflow state change (next step/complete/failed) | 6 fields + validation |
| `WorkflowStatus` | Workflow progress snapshot for monitoring | 9 fields + 2 properties |

**Quick Example:**
```python
# Orchestrator returns instruction
instruction = StepInstruction(
    step_config=archive_step,
    request_id="req-123",
    url="https://example.com",
    component="archive_generator",
    input_schema="ArchiveRequest",
    input_data={"priority": 1}
)

# Transport layer executes instruction
```

> **📖 See [Model Reference → Orchestrator Models](#orchestrator-models)** for complete field documentation

---

### Workflow Models (workflow_models.py)

Runtime state tracking using **Pydantic BaseModel** for validation and serialization.

| Class | Purpose | Features |
|-------|---------|----------|
| `WorkflowStepStatus` | Step/workflow status enum | 5 status values |
| `WorkflowStepInstance` | Individual step progress | 5 fields |
| `WorkflowInstance` | Complete workflow state | 18 fields + 3 methods + 2 properties |

**Quick Example:**
```python
# Track workflow execution
workflow = WorkflowInstance(
    request_id="req-123",
    workflow_name="archaeology_workflow",
    url="https://example.com",
    status=WorkflowStepStatus.IN_PROGRESS,
    steps=[...],
    created_at="2025-01-01T10:00:00Z",
    updated_at="2025-01-01T10:00:00Z"
)

# Mark step completed with results
workflow.mark_step_completed("archive_generation", {
    "snapshot_id": "snap_123",
    "artifacts_created": ["wacz", "html"]
})
```

> **📖 See [Model Reference → Workflow Models](#workflow-models)** for complete field documentation

---

## Implementation Choices

### Dataclasses vs Pydantic

The module uses different base types for different purposes:

| Module | Base Type | Reason |
|--------|-----------|--------|
| `orchestrator_models.py` | **dataclasses** | Simple DTOs for internal communication, no validation needed |
| `workflow_models.py` | **Pydantic BaseModel** | Complex stateful models requiring validation, serialization, and JSON export |

**Why this matters:**
- Dataclasses are lightweight and fast for internal use
- Pydantic provides validation, JSON serialization, and type coercion for persistent state

---

## Key Concepts

### 1. Separation of Concerns

Three distinct types of models serve different purposes:

```text
┌─────────────────────────┐
│  Configuration Models   │  What workflows look like
│  (configs/models.py)    │  → WorkflowConfig, WorkflowStepConfig
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Orchestrator Models    │  Communication between components
│  (models/orchestrator_  │  → StepInstruction, WorkflowTransition
│   models.py)            │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Workflow Models        │  Runtime execution state
│  (models/workflow_      │  → WorkflowInstance, WorkflowStepInstance
│   models.py)            │
└─────────────────────────┘
```

### 2. Data Passing Between Steps

Workflow steps can pass data to subsequent steps via `step_results`:

```python
# Step 1: Archive generation completes
workflow.mark_step_completed("archive_generation", {
    "snapshot_id": "req_123_20250101_120000",
    "archive_path": "/path/to/archive",
    "artifacts_created": ["wacz", "html", "screenshot"]
})

# Step 2: Metadata extraction reads the snapshot_id
archive_results = workflow.step_results["archive_generation"]
snapshot_id = archive_results["snapshot_id"]
document_url = f"http://localhost:8000/api/artifacts/serve?snapshot_id={snapshot_id}"
```

This enables workflows where later steps depend on outputs from earlier steps.

> **📖 See [Usage Patterns → Data Passing](#data-passing-between-steps)** for more examples

### 3. State Management

`WorkflowInstance` provides methods for state transitions:

```python
# Mark step completed (automatically updates timestamps)
workflow.mark_step_completed("step_name", result_data)

# Mark step failed (sets status, error message, end time)
workflow.mark_step_failed("step_name", "error message")

# Mark entire workflow complete (sets status, end time)
workflow.mark_workflow_complete()
```

These methods handle timestamp updates and status changes automatically.

---

## Model Reference

This section provides complete documentation for all models, fields, methods, and properties.

---

## Orchestrator Models

Models for communication between `OrchestratorService` and transport layer.

**File:** `models/orchestrator_models.py`
**Base Type:** Python `@dataclass`
**Purpose:** Transport-agnostic instructions and state transitions

---

### StepInstruction

Transport-agnostic instruction from orchestrator to transport layer.

**Purpose:**
Tells the transport layer which component to invoke and with what data. Contains no transport-specific details (no Kafka topics, no event classes).

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_config` | `WorkflowStepConfig` | Yes | Step configuration from workflow definition |
| `request_id` | `str` | Yes | Unique request identifier |
| `url` | `str` | Yes | URL being processed |
| `component` | `str` | Yes | Component identifier (transport-agnostic) |
| `input_schema` | `str` | Yes | Data schema name (not event model) |
| `input_data` | `Dict[str, Any]` | No | Step-specific input data (default: `{}`) |
| `metadata` | `Optional[Dict[str, Any]]` | No | Additional metadata (default: `None`) |

**Example:**
```python
from models.orchestrator_models import StepInstruction

instruction = StepInstruction(
    step_config=archive_step_config,
    request_id="req-123",
    url="https://arachne.dainst.org/entity/2003166",
    component="archive_generator",
    input_schema="ArchiveRequest",
    input_data={
        "priority": 1,
        "callback_url": "https://example.com/webhook"
    },
    metadata={"source": "api", "user_id": "user-456"}
)
```

**Usage:**
The transport layer uses this instruction to:
1. Look up component mapping in configuration
2. Determine target Kafka topics and event models
3. Create appropriate event
4. Publish to correct topic

---

### WorkflowTransition

Result of a workflow state transition indicating next action.

**Purpose:**
Returned by orchestrator after a step completes or fails. Tells transport layer what to do next.

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | `str` | Yes | Action type: `"execute_step"`, `"workflow_complete"`, `"workflow_failed"` |
| `request_id` | `str` | Yes | Unique request identifier |
| `step_instruction` | `Optional[StepInstruction]` | Conditional | Required if `action="execute_step"` |
| `workflow_instance` | `Optional[WorkflowInstance]` | Conditional | Required if `action` is `complete` or `failed` |
| `error_message` | `Optional[str]` | Conditional | Required if `action="workflow_failed"` |
| `failed_step` | `Optional[str]` | No | Step name where failure occurred |

**Action Types:**

| Action | When Used | Required Fields |
|--------|-----------|-----------------|
| `execute_step` | Next step ready to execute | `step_instruction` |
| `workflow_complete` | All steps completed successfully | `workflow_instance` |
| `workflow_failed` | Workflow failed at a step | `workflow_instance`, `error_message` |

**Validation Rules:**

The `__post_init__` method validates transitions:
- `execute_step` requires `step_instruction`
- `workflow_complete` and `workflow_failed` require `workflow_instance`
- `workflow_failed` requires `error_message`
- Invalid action types raise `ValueError`

**Examples:**

```python
from models.orchestrator_models import WorkflowTransition, StepInstruction

# Next step execution
transition = WorkflowTransition(
    action="execute_step",
    request_id="req-123",
    step_instruction=StepInstruction(...)
)

# Workflow completion
transition = WorkflowTransition(
    action="workflow_complete",
    request_id="req-123",
    workflow_instance=completed_workflow
)

# Workflow failure
transition = WorkflowTransition(
    action="workflow_failed",
    request_id="req-123",
    workflow_instance=failed_workflow,
    error_message="Archive generation timeout after 300s",
    failed_step="archive_generation"
)

# Invalid transition (raises ValueError)
try:
    transition = WorkflowTransition(
        action="execute_step",
        request_id="req-123"
        # Missing step_instruction!
    )
except ValueError as e:
    print(e)  # "execute_step action requires step_instruction"
```

---

### WorkflowStatus

Snapshot of workflow progress for monitoring and status queries.

**Purpose:**
Provides a read-only view of workflow state without exposing full `WorkflowInstance` internals.

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | `str` | Yes | Unique request identifier |
| `workflow_name` | `str` | Yes | Name of workflow being executed |
| `url` | `str` | Yes | URL being processed |
| `current_step` | `Optional[str]` | No | Currently executing step (None if pending/complete) |
| `completed_steps` | `set[str]` | Yes | Set of completed step names |
| `total_steps` | `int` | Yes | Total number of steps in workflow |
| `status` | `str` | Yes | Overall status: `"pending"`, `"in_progress"`, `"completed"`, `"failed"` |
| `error_message` | `Optional[str]` | No | Error message if failed |
| `failed_step` | `Optional[str]` | No | Step name where failure occurred |

**Computed Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `progress_percentage` | `float` | Completion percentage (0.0 - 100.0) |
| `is_complete` | `bool` | True if workflow in terminal state (`completed` or `failed`) |

**Example:**
```python
from models.orchestrator_models import WorkflowStatus

status = WorkflowStatus(
    request_id="req-123",
    workflow_name="archaeology_workflow",
    url="https://arachne.dainst.org/entity/2003166",
    current_step="metadata_extraction",
    completed_steps={"archive_generation"},
    total_steps=3,
    status="in_progress"
)

print(f"Progress: {status.progress_percentage}%")  # 33.33%
print(f"Complete: {status.is_complete}")  # False
```

---

## Workflow Models

Models for tracking runtime workflow execution state.

**File:** `models/workflow_models.py`
**Base Type:** Pydantic `BaseModel`
**Purpose:** Stateful models for workflow execution with validation and serialization

---

### WorkflowStepStatus

Enum representing step and workflow status values.

**Type:** `str` Enum
**Base:** `str, Enum`

**Values:**

| Value | String | Description | When Used |
|-------|--------|-------------|-----------|
| `PENDING` | `"pending"` | Not started yet | Initial state for steps |
| `IN_PROGRESS` | `"in_progress"` | Currently executing | Step is running |
| `COMPLETED` | `"completed"` | Finished successfully | Step succeeded |
| `FAILED` | `"failed"` | Encountered error | Step failed |
| `TIMEOUT` | `"timeout"` | Exceeded time limit | Step timed out |

**State Transitions:**

```text
PENDING → IN_PROGRESS → COMPLETED
              ↓
            FAILED
              ↓
            TIMEOUT
```

**Example:**
```python
from models.workflow_models import WorkflowStepStatus

status = WorkflowStepStatus.PENDING
assert status == "pending"  # Can compare with strings

# Check status
if status == WorkflowStepStatus.IN_PROGRESS:
    print("Step is running")

# Iterate all statuses
for status in WorkflowStepStatus:
    print(f"{status.name}: {status.value}")
```

---

### WorkflowStepInstance

Runtime state for a single workflow step.

**Purpose:**
Tracks execution progress of one step, including timing and error information.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | - | Step name (matches workflow configuration) |
| `status` | `WorkflowStepStatus` | `PENDING` | Current step status |
| `started_at` | `Optional[str]` | `None` | ISO 8601 timestamp when step started |
| `completed_at` | `Optional[str]` | `None` | ISO 8601 timestamp when step completed |
| `error_message` | `Optional[str]` | `None` | Error description if step failed |

**Example:**
```python
from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus

# Create pending step
step = WorkflowStepInstance(name="archive_generation")
assert step.status == WorkflowStepStatus.PENDING

# Start step
step.status = WorkflowStepStatus.IN_PROGRESS
step.started_at = "2025-01-17T10:00:00Z"

# Complete step
step.status = WorkflowStepStatus.COMPLETED
step.completed_at = "2025-01-17T10:05:00Z"

# Failed step
failed_step = WorkflowStepInstance(
    name="metadata_extraction",
    status=WorkflowStepStatus.FAILED,
    started_at="2025-01-17T10:05:00Z",
    error_message="Connection timeout to document server"
)
```

---

### WorkflowInstance

Complete runtime state for an entire workflow execution.

**Purpose:**
Represents a single workflow execution for a specific request, tracking all steps, progress, timing, and results.

**Core Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `request_id` | `str` | - | Unique request identifier |
| `workflow_name` | `str` | - | Name of workflow being executed |
| `url` | `str` | - | URL being processed |
| `status` | `WorkflowStepStatus` | - | Overall workflow status |
| `steps` | `List[WorkflowStepInstance]` | - | List of workflow steps and their status |
| `created_at` | `str` | - | ISO 8601 timestamp when workflow created |
| `updated_at` | `str` | - | ISO 8601 timestamp of last update |

**Optional Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `callback_url` | `Optional[str]` | `None` | Optional webhook URL for push notifications |
| `metadata` | `Dict[str, Any]` | `{}` | Additional workflow metadata |

**Enhanced State Tracking:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `current_step` | `Optional[str]` | `None` | Name of currently executing step |
| `completed_steps` | `Set[str]` | `set()` | Set of completed step names |
| `failed_steps` | `Set[str]` | `set()` | Set of failed step names |
| `start_time` | `Optional[datetime]` | `None` | Datetime when workflow execution started |
| `end_time` | `Optional[datetime]` | `None` | Datetime when workflow execution ended |
| `step_results` | `Dict[str, Any]` | `{}` | Results from each completed step (for data passing) |
| `error_message` | `Optional[str]` | `None` | Error message if workflow failed |
| `failed_at_step` | `Optional[str]` | `None` | Step name where workflow failed |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `mark_step_completed` | `step_name: str, result_data: Optional[Dict]` | `None` | Mark step as completed, store results, update timestamp |
| `mark_step_failed` | `step_name: str, error_message: str` | `None` | Mark step as failed, set workflow to FAILED, record error |
| `mark_workflow_complete` | - | `None` | Mark entire workflow as COMPLETED, set end time |

**Computed Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_complete` | `bool` | True if workflow in terminal state (COMPLETED or FAILED) |
| `processing_time_seconds` | `Optional[float]` | Total processing time if workflow ended |

**Example - Basic Usage:**
```python
from models.workflow_models import (
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowStepStatus
)
from datetime import datetime, timezone

# Create workflow instance
workflow = WorkflowInstance(
    request_id="req-123",
    workflow_name="archaeology_workflow",
    url="https://arachne.dainst.org/entity/2003166",
    status=WorkflowStepStatus.PENDING,
    steps=[
        WorkflowStepInstance(name="archive_generation"),
        WorkflowStepInstance(name="metadata_extraction"),
        WorkflowStepInstance(name="doi_assignment")
    ],
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat(),
    start_time=datetime.now(timezone.utc)
)
```

**Example - State Transitions:**
```python
# Mark step completed with results
workflow.mark_step_completed("archive_generation", {
    "snapshot_id": "req_req-123_20250117_100000",
    "archive_path": "archives/arachne.../req_req-123_20250117_100000",
    "artifacts_created": ["wacz", "html", "screenshot"]
})

# Access completed step results
archive_results = workflow.step_results["archive_generation"]
snapshot_id = archive_results["snapshot_id"]

# Mark step failed
workflow.mark_step_failed(
    "metadata_extraction",
    "Connection timeout to document server after 30s"
)
# workflow.status is now FAILED
# workflow.failed_at_step is "metadata_extraction"
# workflow.end_time is set

# Mark workflow complete (all steps succeeded)
workflow.mark_workflow_complete()
# workflow.status is now COMPLETED
# workflow.end_time is set

# Check if finished
if workflow.is_complete:
    print(f"Workflow finished in {workflow.processing_time_seconds}s")
```

**Example - Serialization:**
```python
# To JSON
json_str = workflow.model_dump_json()

# From JSON
workflow = WorkflowInstance.model_validate_json(json_str)

# To dict
data = workflow.model_dump()

# Partial update
workflow_dict = workflow.model_dump()
workflow_dict["status"] = WorkflowStepStatus.COMPLETED
updated_workflow = WorkflowInstance(**workflow_dict)
```

---

## Usage Patterns

Common patterns for working with models.

### Creating a Workflow Instance

```python
from datetime import datetime, timezone
from models.workflow_models import (
    WorkflowInstance,
    WorkflowStepInstance,
    WorkflowStepStatus
)

def create_workflow_instance(request_id: str, url: str, workflow_config):
    """Create new workflow instance from configuration."""

    # Create step instances from config
    steps = [
        WorkflowStepInstance(name=step.name)
        for step in workflow_config.steps
    ]

    now = datetime.now(timezone.utc).isoformat()

    return WorkflowInstance(
        request_id=request_id,
        workflow_name=workflow_config.name,
        url=url,
        status=WorkflowStepStatus.PENDING,
        steps=steps,
        created_at=now,
        updated_at=now,
        start_time=datetime.now(timezone.utc)
    )
```

### Data Passing Between Steps

```python
# Step 1 completes and stores snapshot_id
workflow.mark_step_completed("archive_generation", {
    "snapshot_id": "req_123_20250117_100000",
    "archive_path": "/path/to/archive",
    "artifacts_created": ["wacz", "html", "screenshot"]
})

# Step 2 reads snapshot_id from previous step
archive_results = workflow.step_results.get("archive_generation", {})
snapshot_id = archive_results.get("snapshot_id")

if snapshot_id:
    document_url = (
        f"http://localhost:8000/api/artifacts/serve?"
        f"snapshot_id={snapshot_id}&type=dom-snapshot.html"
    )
    print(f"Document URL for metadata extraction: {document_url}")
```

### Monitoring Workflow Progress

```python
from models.orchestrator_models import WorkflowStatus

def get_workflow_status(workflow: WorkflowInstance) -> WorkflowStatus:
    """Create status snapshot for monitoring."""

    return WorkflowStatus(
        request_id=workflow.request_id,
        workflow_name=workflow.workflow_name,
        url=workflow.url,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps,
        total_steps=len(workflow.steps),
        status=workflow.status.value,
        error_message=workflow.error_message,
        failed_step=workflow.failed_at_step
    )

# Use status
status = get_workflow_status(workflow)
print(f"Progress: {status.progress_percentage}%")
print(f"Current step: {status.current_step}")
print(f"Completed: {len(status.completed_steps)}/{status.total_steps}")
```

### Handling Workflow Transitions

```python
from models.orchestrator_models import WorkflowTransition

# After step completes, orchestrator returns transition
transition = orchestrator.step_completed(request_id, "archive_generation", results)

# Transport layer handles transition
if transition.action == "execute_step":
    # Execute next step
    kafka_service.publish_step_request(transition.step_instruction)

elif transition.action == "workflow_complete":
    # Publish completion event
    kafka_service.publish_workflow_complete(transition.workflow_instance)

elif transition.action == "workflow_failed":
    # Publish failure event
    kafka_service.publish_workflow_failed(
        transition.workflow_instance,
        transition.error_message,
        transition.failed_step
    )
```

### Error Handling

```python
try:
    # Process step
    result = process_archive_step(workflow)
    workflow.mark_step_completed("archive_generation", result)

except Exception as e:
    # Mark step as failed
    workflow.mark_step_failed("archive_generation", str(e))

    # Log failure
    logger.error(
        f"Step failed: {workflow.failed_at_step}",
        extra={
            "request_id": workflow.request_id,
            "error": workflow.error_message
        }
    )
```

---

## Validation and Serialization

### Pydantic Models

`WorkflowStepInstance` and `WorkflowInstance` use Pydantic for:

**Validation:**
- Type checking at instantiation
- Field validation (e.g., non-empty strings)
- Enum validation

**Serialization:**
- JSON export via `model_dump_json()`
- Dict export via `model_dump()`
- JSON import via `model_validate_json()`

**Example:**
```python
# Invalid data raises ValidationError
try:
    workflow = WorkflowInstance(
        request_id="",  # Empty string
        workflow_name="test",
        url="https://example.com",
        status="invalid_status",  # Not a valid enum value
        steps=[],
        created_at="not-a-timestamp",
        updated_at="not-a-timestamp"
    )
except ValidationError as e:
    print(e)
```

### Dataclass Models

`StepInstruction`, `WorkflowTransition`, and `WorkflowStatus` use dataclasses for:

**Simplicity:**
- Lightweight structure
- No validation overhead
- Fast instantiation

**Validation:**
- Only `WorkflowTransition` validates in `__post_init__`
- Other models assume correct usage

---

## Design Rationale

### Why Two Types of Models?

| Aspect | Orchestrator Models | Workflow Models |
|--------|-------------------|-----------------|
| **Base Type** | Dataclass | Pydantic BaseModel |
| **Purpose** | Internal communication | Persistent state |
| **Validation** | Minimal (except WorkflowTransition) | Full validation |
| **Serialization** | Not needed | JSON/dict export |
| **Performance** | Faster (no validation) | Slightly slower |
| **Use Case** | Transient instructions | Long-lived state |

### State Management Philosophy

- **Immutable history** - Completed/failed steps don't change state
- **Explicit transitions** - Methods enforce valid state changes
- **Timestamp tracking** - All transitions automatically timestamped
- **Self-contained** - `WorkflowInstance` has all info for resumption

---

## Related Documentation

- **Configuration Models** - See [configs/models.py](../configs/models.py) for workflow configuration structures
- **Event Models** - See [docs/EVENT_MODELS.md](../docs/EVENT_MODELS.md) for Kafka event structures
- **Workflow Documentation** - See [docs/WORKFLOW_MODELS.md](../docs/WORKFLOW_MODELS.md) for detailed workflow model explanations
