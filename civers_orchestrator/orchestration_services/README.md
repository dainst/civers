# Orchestration Services

Core business logic for workflow orchestration with modular, maintainable architecture.

## Overview

The orchestration services provide **pure business logic** for workflow execution through a modular architecture. The system is composed of specialized components, each with a single, well-defined responsibility.

**Key Principle:** No knowledge of transport mechanisms (Kafka, HTTP, etc.) - returns instructions that the transport layer executes.

---

## Architecture

### Modular Design

The orchestration services follow the **Facade Pattern** with **Dependency Injection**:

```text
┌─────────────────────────────────────────────────────────────┐
│                  OrchestratorService                        │
│                    (Facade / Coordinator)                    │
│                                                              │
│  Public API: start_workflow(), step_completed(),            │
│             step_failed(), get_workflow_status()            │
└───────────────┬──────────────┬──────────────┬───────────────┘
                │              │              │
                ▼              ▼              ▼
    ┌──────────────────┐ ┌─────────────┐ ┌──────────────┐
    │ WorkflowResolver │ │ StepExecutor│ │TimeoutMonitor│
    │                  │ │             │ │              │
    │ • Domain match   │ │ • Step      │ │ • Timeout    │
    │ • Dependencies   │ │   instruct. │ │   detection  │
    │ • Navigation     │ │ • Transform │ │ • Batch      │
    └──────────────────┘ └─────────────┘ │   checking   │
                                          └──────────────┘
                │
                ▼
    ┌──────────────────────────┐
    │  WorkflowStateStore      │
    │                          │
    │ • Thread-safe storage    │
    │ • Memory management      │
    │ • Cleanup automation     │
    └──────────────────────────┘
```

### Module Responsibilities

| Module | Lines | Responsibility | Key Features |
|--------|-------|----------------|--------------|
| **orchestrator_service.py** | 363 | Facade & Coordination | Public API, orchestration logic |
| **workflow_state_store.py** | 225 | State Management | Thread safety, memory limits, cleanup |
| **workflow_resolver.py** | 303 | Resolution Logic | Domain matching, dependencies, navigation |
| **step_executor.py** | 123 | Step Execution | Instruction creation, data transformers |
| **timeout_monitor.py** | 146 | Timeout Management | Timeout detection, batch monitoring |
| **exceptions.py** | 58 | Custom Exceptions | Domain-specific error types |
| **data_transformers.py** | 280 | Data Transformation | Step-to-step data passing |

**Total:** 1,498 lines across 7 focused modules (vs previous 812-line monolith)

---

## Module Details

### 1. OrchestratorService (Main Facade)

**File:** `orchestrator_service.py`
**Purpose:** Public API and coordination between specialized components

**Key Methods:**

```python
class OrchestratorService:
    def start_workflow(request_id, url, workflow_name=None) -> StepInstruction
    def step_completed(request_id, step_name, result_data) -> WorkflowTransition
    def step_failed(request_id, step_name, error_message) -> WorkflowTransition
    def get_workflow_state(request_id) -> WorkflowInstance
    def get_workflow_status(request_id) -> WorkflowStatus
    def cleanup_completed_workflows(max_age_seconds) -> int
    def check_step_timeout(request_id) -> Optional[WorkflowTransition]
    def check_all_timeouts() -> List[WorkflowTransition]
```

**Initialization:**
```python
# Composes specialized components via dependency injection
orchestrator = OrchestratorService(config)
# Internally creates:
# - WorkflowStateStore for state management
# - WorkflowResolver for domain/dependency resolution
# - StepExecutor for instruction creation
# - TimeoutMonitor for timeout detection
```

**Design Pattern:** Facade - Provides unified interface while delegating to specialized components

---

### 2. WorkflowStateStore

**File:** `workflow_state_store.py`
**Purpose:** Thread-safe workflow state storage with memory management

**Features:**
- **Thread Safety:** All operations protected by `threading.RLock`
- **Memory Management:** Automatic cleanup of old workflows
- **Storage Limits:** Configurable maximum (default: 10,000 workflows)
- **Bulk Operations:** Query workflows by status, count statistics

**Key Methods:**

```python
class WorkflowStateStore:
    def store_workflow(request_id, workflow) -> None
    def get_workflow(request_id) -> Optional[WorkflowInstance]
    def update_workflow(request_id, workflow) -> None
    def remove_workflow(request_id) -> bool
    def cleanup_completed_workflows(max_age_seconds) -> int
    def get_all_active() -> List[str]
    def get_count_by_status() -> Dict[str, int]
```

**Thread Safety Example:**
```python
with self._state_lock:
    self.workflow_states[request_id] = workflow
    self._enforce_workflow_limit()
```

**Memory Management:**
- Automatic cleanup of workflows older than configured age
- Enforces maximum workflow limit by removing oldest completed workflows
- Logs cleanup operations for monitoring

---

### 3. WorkflowResolver

**File:** `workflow_resolver.py`
**Purpose:** Domain matching, dependency resolution, and workflow navigation

**Responsibilities:**
1. **Domain Matching:** Map URLs to workflows using three-tier strategy
2. **Dependency Resolution:** Topological sort using Kahn's algorithm
3. **Navigation:** Determine first step, next step, completion status

**Domain Matching Strategy:**

```text
1. Exact Match      arachne.dainst.org → archaeology_workflow
2. Wildcard Match   *.dainst.org → dainst_default_workflow
3. Default Fallback default → standard_archive_workflow
```

**Key Methods:**

```python
class WorkflowResolver:
    def match_domain_to_workflow(url) -> str
    def get_workflow(workflow_name) -> WorkflowConfig
    def get_first_step(workflow_name) -> WorkflowStepConfig
    def get_next_step(workflow, completed_steps) -> Optional[WorkflowStepConfig]
    def is_workflow_complete(workflow, completed_steps) -> bool
    def resolve_dependencies(steps) -> List[List[WorkflowStepConfig]]
```

**Dependency Resolution:**

Uses **Kahn's Algorithm** for topological sorting:
```python
# Resolves dependencies and detects circular references
execution_layers = resolver.resolve_dependencies(workflow.steps)
# Returns: [[step1, step2], [step3], [step4, step5]]
# Each layer can execute in parallel
```

---

### 4. StepExecutor

**File:** `step_executor.py`
**Purpose:** Create step instructions with data transformer support

**Responsibilities:**
- Build base input data for steps
- Apply data transformers from workflow configuration
- Construct StepInstruction objects for transport layer

**Key Features:**
- **No Hardcoded Logic:** All step-to-step data passing is configuration-driven
- **Data Transformers:** Flexible transformation framework
- **Error Handling:** Clear error messages for missing required fields

**Key Methods:**

```python
class StepExecutor:
    def create_step_instruction(workflow_instance, step) -> StepInstruction
```

**Data Transformer Application:**

```python
# Applies transformers from workflow configuration
if step.input_transformers:
    for transformer_config in step.input_transformers:
        # Get value from previous step
        source_value = workflow_instance.step_results.get(
            transformer_config.source_step
        ).get(transformer_config.source_field)

        # Apply transformer
        transformed_value = apply_transformer(
            transformer_config.transformer,
            source_value,
            transformer_config.transformer_config,
            context
        )

        # Add to step input
        input_data[transformer_config.target_field] = transformed_value
```

**Example Configuration:**

```yaml
# In workflows.yaml
steps:
  - name: metadata_extraction
    input_transformers:
      - source_step: "archive_generation"
        source_field: "snapshot_id"
        target_field: "document_url"
        transformer: "build_web_interface_url"
        required: true
```

---

### 5. TimeoutMonitor

**File:** `timeout_monitor.py`
**Purpose:** Monitor and detect step timeout violations

**Features:**
- **Single Workflow Check:** Check individual workflow for timeout
- **Batch Checking:** Check all active workflows efficiently
- **Timeout Marking:** Automatically marks timed-out steps

**Key Methods:**

```python
class TimeoutMonitor:
    def check_step_timeout(request_id) -> Optional[Dict]
    def check_all_timeouts() -> List[Dict]
```

**Timeout Detection:**

```python
# Calculates elapsed time and compares to configured timeout
elapsed = (datetime.now(timezone.utc) - step_started_at).total_seconds()
if elapsed > step_config.timeout_seconds:
    # Mark as timed out and return timeout info
    step_instance.status = WorkflowStepStatus.TIMEOUT
    return timeout_info
```

**Usage in Background Task:**

```python
# In main.py or background monitoring
async def timeout_monitor_task():
    while True:
        timeout_infos = orchestrator.check_all_timeouts()
        for info in timeout_infos:
            # Handle timeout (already marked as failed by orchestrator)
            logger.error(f"Workflow {info['request_id']} timed out")

        await asyncio.sleep(10)  # Check every 10 seconds
```

---

### 6. Exceptions

**File:** `exceptions.py`
**Purpose:** Domain-specific exception classes

**Exception Types:**

```python
class CircularDependencyError(Exception):
    """Raised when workflow steps have circular dependencies."""

class WorkflowNotFoundError(Exception):
    """Raised when requested workflow doesn't exist in configuration."""
```

**Usage:**

```python
try:
    workflow = resolver.get_workflow("unknown_workflow")
except WorkflowNotFoundError as e:
    logger.error(f"Workflow not found: {e.workflow_name}")
    logger.info(f"Available workflows: {e.available_workflows}")
```

---

### 7. Data Transformers

**File:** `data_transformers.py`
**Purpose:** Framework for transforming data between workflow steps

**Key Components:**
- **DataTransformer** base class
- **Built-in transformers** (build_web_interface_url, pass_through)
- **Transformer registry** for extensibility
- **apply_transformer()** function

See [data_transformers.py](data_transformers.py) for detailed documentation.

---

## How It Works

### Complete Workflow Execution Flow

```text
┌──────────────────────────────────────────────────────────────────┐
│ 1. Request Arrives                                               │
│    URL: https://arachne.dainst.org/entity/123                    │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. OrchestratorService.start_workflow()                          │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ a. WorkflowResolver.match_domain_to_workflow()          │  │
│    │    → Matches "arachne.dainst.org" to "archaeology_wf"   │  │
│    │                                                           │  │
│    │ b. Create WorkflowInstance                               │  │
│    │    → Initialize state, steps, metadata                   │  │
│    │                                                           │  │
│    │ c. WorkflowStateStore.store_workflow()                   │  │
│    │    → Thread-safe storage with limit enforcement          │  │
│    │                                                           │  │
│    │ d. WorkflowResolver.get_first_step()                     │  │
│    │    → Returns step with no dependencies                   │  │
│    │                                                           │  │
│    │ e. StepExecutor.create_step_instruction()                │  │
│    │    → Creates instruction for "archive_generation"        │  │
│    └─────────────────────────────────────────────────────────┘  │
│    Returns: StepInstruction                                      │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Transport Layer Executes Step                                 │
│    → Publishes ArchiveRequestEvent to Kafka                      │
│    → Archive service processes and publishes ArchiveCompleted    │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. OrchestratorService.step_completed()                          │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ a. WorkflowStateStore.get_workflow()                     │  │
│    │    → Retrieves workflow instance (thread-safe)           │  │
│    │                                                           │  │
│    │ b. workflow_instance.mark_step_completed()               │  │
│    │    → Stores result_data: {"snapshot_id": "snap_123"}     │  │
│    │                                                           │  │
│    │ c. WorkflowResolver.is_workflow_complete()               │  │
│    │    → Checks if all steps done (No - more steps)          │  │
│    │                                                           │  │
│    │ d. WorkflowResolver.get_next_step()                      │  │
│    │    → Returns "metadata_extraction" (dependencies met)    │  │
│    │                                                           │  │
│    │ e. StepExecutor.create_step_instruction()                │  │
│    │    → Applies data transformers:                          │  │
│    │      • Gets snapshot_id from archive results             │  │
│    │      • Transforms to document_url via transformer        │  │
│    │    → Creates instruction with transformed data           │  │
│    └─────────────────────────────────────────────────────────┘  │
│    Returns: WorkflowTransition(action="execute_step")            │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. Transport Layer Executes Next Step                            │
│    → Publishes MetadataRequestEvent with document_url            │
│    → Metadata service processes and publishes MetadataCompleted  │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 6. OrchestratorService.step_completed()                          │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ a. WorkflowResolver.is_workflow_complete()               │  │
│    │    → Checks if all steps done (Yes - all complete)       │  │
│    │                                                           │  │
│    │ b. workflow_instance.mark_workflow_complete()            │  │
│    │    → Sets status, end_time                               │  │
│    │                                                           │  │
│    │ c. WorkflowStateStore.update_workflow()                  │  │
│    │    → Persists final state                                │  │
│    └─────────────────────────────────────────────────────────┘  │
│    Returns: WorkflowTransition(action="workflow_complete")       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Code Examples

### Starting a Workflow

```python
from orchestration_services.orchestrator_service import OrchestratorService

# Initialize orchestrator
orchestrator = OrchestratorService(config)

# Start workflow
instruction = orchestrator.start_workflow(
    request_id="req-123",
    url="https://arachne.dainst.org/entity/456",
    callback_url="https://api.example.com/webhook",
    metadata={"priority": 1, "user_id": "user-789"}
)

# instruction contains:
# - component: "archive_generator"
# - input_schema: "ArchiveRequest"
# - input_data: {"url": "...", "callback_url": "...", "priority": 1}
```

### Handling Step Completion

```python
# Archive generation completed
transition = orchestrator.step_completed(
    request_id="req-123",
    step_name="archive_generation",
    result_data={
        "snapshot_id": "req_123_20250117_120000",
        "archive_path": "/path/to/archive",
        "file_count": 42
    }
)

# transition contains:
# - action: "execute_step"
# - step_instruction: StepInstruction for metadata_extraction
# - workflow_instance: Current workflow state
```

### Handling Step Failure

```python
# Metadata extraction failed
transition = orchestrator.step_failed(
    request_id="req-123",
    step_name="metadata_extraction",
    error_message="Failed to parse document: Invalid HTML structure"
)

# transition contains:
# - action: "workflow_failed"
# - error_message: "Failed to parse document: Invalid HTML structure"
# - failed_step: "metadata_extraction"
# - workflow_instance: Final workflow state
```

### Querying Workflow Status

```python
# Get detailed workflow status
status = orchestrator.get_workflow_status("req-123")

# status contains:
# - request_id: "req-123"
# - workflow_name: "archaeology_workflow"
# - current_step: "metadata_extraction"
# - completed_steps: {"archive_generation"}
# - total_steps: 3
# - status: "in_progress"
# - progress_percentage: 33.33
```

### Memory Management

```python
# Clean up workflows older than 1 hour
removed_count = orchestrator.cleanup_completed_workflows(
    max_age_seconds=3600
)
logger.info(f"Cleaned up {removed_count} workflows")

# Can be run periodically in background task
async def cleanup_task():
    while True:
        await asyncio.sleep(3600)  # Every hour
        orchestrator.cleanup_completed_workflows()
```

### Timeout Monitoring

```python
# Check specific workflow for timeout
transition = orchestrator.check_step_timeout("req-123")
if transition:
    # Workflow timed out, transition contains failure info
    logger.error(f"Workflow timed out: {transition.error_message}")

# Check all active workflows (batch)
transitions = orchestrator.check_all_timeouts()
for transition in transitions:
    # Handle each timeout
    logger.error(f"Request {transition.request_id} timed out")
```

---

## Design Principles

### 1. Transport Agnostic

The orchestrator has **zero knowledge** of transport mechanisms:

```python
# ✅ Good - Returns instructions
return StepInstruction(
    component="archive_generator",
    input_schema="ArchiveRequest",
    input_data={"url": url}
)

# ❌ Bad - Direct transport operations
kafka_producer.send("archive.requests", data)
```

### 2. Single Responsibility

Each module has **one clear purpose**:

- **WorkflowStateStore** → Only state management
- **WorkflowResolver** → Only resolution logic
- **StepExecutor** → Only instruction creation
- **TimeoutMonitor** → Only timeout detection

### 3. Dependency Injection

Components receive their dependencies via constructor:

```python
class OrchestratorService:
    def __init__(self, config):
        # Dependencies injected at initialization
        self.state_store = WorkflowStateStore(max_stored_workflows=10000)
        self.resolver = WorkflowResolver(workflows, domains)
        self.executor = StepExecutor(config)
        self.timeout_monitor = TimeoutMonitor(self.state_store, workflows)
```

**Benefits:**
- Easy to test (can inject mocks)
- Loose coupling between components
- Clear dependency graph

### 4. Immutable Returns

Methods return new objects rather than modifying global state:

```python
# Returns new StepInstruction
instruction = orchestrator.start_workflow(...)

# Returns new WorkflowTransition
transition = orchestrator.step_completed(...)
```

### 5. Thread Safety

All state access is protected by locks in `WorkflowStateStore`:

```python
with self._state_lock:
    self.workflow_states[request_id] = workflow
    self._enforce_workflow_limit()
```

### 6. Fail Fast

Clear validation and error messages:

```python
if not request_id:
    raise ValueError("request_id cannot be empty")

if transformer_config.required and not source_value:
    raise ValueError(
        f"Required field '{source_field}' missing from "
        f"step '{source_step}' results. "
        f"Available fields: {list(source_results.keys())}"
    )
```

---

## Testing Strategy

### Unit Testing Each Module

```python
# Test WorkflowStateStore independently
def test_workflow_state_store():
    store = WorkflowStateStore(max_stored_workflows=100)
    workflow = create_test_workflow()

    store.store_workflow("req-1", workflow)
    assert store.get_workflow("req-1") == workflow
    assert store.get_total_count() == 1

# Test WorkflowResolver independently
def test_workflow_resolver():
    resolver = WorkflowResolver(test_workflows, test_domains)

    workflow_name = resolver.match_domain_to_workflow(
        "https://arachne.dainst.org/entity/123"
    )
    assert workflow_name == "archaeology_workflow"

# Test StepExecutor independently
def test_step_executor():
    executor = StepExecutor(test_config)
    workflow = create_workflow_with_results()
    step = create_test_step_with_transformers()

    instruction = executor.create_step_instruction(workflow, step)
    assert instruction.input_data["document_url"].startswith("http://")
```

### Integration Testing

```python
def test_complete_workflow_execution():
    orchestrator = OrchestratorService(config)

    # Start workflow
    instruction = orchestrator.start_workflow(
        request_id="test-1",
        url="https://test.example.com"
    )
    assert instruction.component == "archive_generator"

    # Complete first step
    transition = orchestrator.step_completed(
        request_id="test-1",
        step_name="archive_generation",
        result_data={"snapshot_id": "snap-123"}
    )
    assert transition.action == "execute_step"

    # Complete second step
    transition = orchestrator.step_completed(
        request_id="test-1",
        step_name="metadata_extraction"
    )
    assert transition.action == "workflow_complete"
```

---

## Performance Considerations

### Memory Management

- **Automatic Cleanup:** Old workflows removed automatically
- **Storage Limits:** Configurable maximum (default: 10,000)
- **Efficient Removal:** O(n log n) sorting for cleanup

### Thread Safety

- **RLock Usage:** Reentrant locks prevent deadlocks
- **Minimal Lock Scope:** Locks held for shortest time possible
- **No Nested Locks:** Simple lock hierarchy

### Scalability

Current design is suitable for:
- ✅ **Single Instance:** Full thread safety
- ✅ **Low-Medium Load:** 10,000 concurrent workflows
- ⚠️ **High Load / Multi-Instance:** Requires external state store (Redis, PostgreSQL)

**Future Enhancement:** Pluggable state store interface for distributed deployments.



## Future Enhancements

### Pluggable State Store

```python
# Current: In-memory only
state_store = WorkflowStateStore()

# Future: Pluggable backends
state_store = RedisStateStore(connection)
state_store = PostgreSQLStateStore(connection)
```

### Distributed Locking

For multi-instance deployments:

```python
# Current: Threading locks (single instance)
with self._state_lock:
    self.workflow_states[request_id] = workflow

# Future: Distributed locks
with self.distributed_lock.acquire(f"workflow:{request_id}"):
    self.state_store.store_workflow(request_id, workflow)
```

### Metrics Collection

Add metrics to each component:

```python
class WorkflowStateStore:
    def store_workflow(self, request_id, workflow):
        with self._metrics.timer("store_workflow_duration"):
            # ... storage logic ...
        self._metrics.increment("workflows_stored")
```

### Event Hooks

Lifecycle hooks for monitoring and extension:

```python
orchestrator.on_workflow_started(lambda wf: log_start(wf))
orchestrator.on_workflow_completed(lambda wf: notify_user(wf))
orchestrator.on_workflow_failed(lambda wf: alert_ops(wf))
```

---

## Related Documentation

- **[REFACTORING_PLAN.md](REFACTORING_PLAN.md)** - Detailed refactoring plan and rationale
- **[data_transformers.py](data_transformers.py)** - Data transformer framework documentation
- **[../configs/README.md](../configs/README.md)** - Configuration system documentation
- **[../models/README.md](../models/README.md)** - Data models documentation

---

## Summary

The orchestration services provide a **clean, modular architecture** for workflow execution:

- ✅ **Single Responsibility** - Each module has one clear purpose
- ✅ **Testable** - Components can be tested independently
- ✅ **Maintainable** - 55% smaller main file, focused modules
- ✅ **Thread-Safe** - All state access protected by locks
- ✅ **Memory-Managed** - Automatic cleanup, configurable limits
- ✅ **Transport-Agnostic** - No Kafka/HTTP knowledge
- ✅ **Extensible** - Easy to add new components or features
- ✅ **Production-Ready** - Comprehensive error handling, logging

**Architecture:** Facade Pattern with Dependency Injection
**Lines of Code:** 1,498 lines across 7 modules (vs 812-line monolith)
**Public API:** Unchanged - full backward compatibility
