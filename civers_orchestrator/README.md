# CiVers Orchestrator 🧠

The central brain of the CiVers web archiving ecosystem. The Orchestrator manages the lifecycle of archiving requests, coordinating between specialized microservices to transform a simple URL into a preserved digital asset.

---

## 🏛️ System Architecture

The Orchestrator acts as the "Conductor" in a choreographic microservice architecture. It doesn't perform the work itself; instead, it tells other services when it's their turn to act.

### The Big Picture

```text
      ┌────────────────┐           ┌──────────────────┐
      │  User/System   │           │ Archive Generator│
      └───────┬────────┘           └────────┬─────────┘
              │ 1. Request URL              │ 2. Archive Files
              ▼                             ▼
        ╔═══════════════╗           ╔═══════════════╗
        ║    KAFKA      ║◄══════════║  WEB INTERFACE║
        ║  (Messenger)  ║           ║   (Storage)   ║
        ╚═══════════════╝           ╚═══════════════╝
              ▲      │                      ▲
              │      │ 3. Status/Events     │ 4. Metadata
      ┌───────┴──────▼─┐           ┌────────┴─────────┐
      │  ORCHESTRATOR  │           │Metadata Extractor│
      │   (The Brain)  │           └──────────────────┘
      └────────────────┘
```

### Internal "Separation of Concerns"

To keep the code clean and maintainable, we strictly separate **Decision Making** from **Communication**:

* **The Brain (`OrchestratorService`)**: Pure logic. It knows that "Step A must follow Step B" but has no idea how Kafka works.
* **The Voice (`KafkaTransportService`)**: The implementation. It knows how to send and receive messages but doesn't understand the "Why" behind the workflow.

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.12+**
* **[uv](https://github.com/astral-sh/uv)**: A fast Python package manager.
* **Docker**: To run the Kafka messenger locally.

### 1. Basic Setup

```bash
# Production dependencies only (what the app needs to run)
uv sync

# Development dependencies (required for tests and scripts)
# Includes kafka-python (used by test helpers and scripts/test_workflow.py),
# pytest, ruff, mypy, and aiokafka extras.
uv sync --extra dev

# Start the Kafka broker and UI
docker compose up -d kafka kafka-ui
```

> **Why two packages?**  
> The production app uses **aiokafka** (async).  
> The manual test script and test helpers use **kafka-python** (sync, simpler for CLI tooling).  
> `kafka-python` lives in `[project.optional-dependencies] dev` and is never shipped to production.

> **Shared config package:** the Orchestrator depends on **`civers_common`**
> (a `uv` workspace member) for its base config models, domain resolution mixin,
> and YAML loader. Docker builds therefore use the **repo root** as the build
> context (`docker compose build orchestrator`), not this sub-directory.
> See `configs/README.md` for what ORCH inherits vs. keeps service-specific.

### 2. Running the Application

| Environment | Command | Use Case |
| :--- | :--- | :--- |
| **Development** | `CONFIG_ENVIRONMENT=development uv run python main.py` | Default for local coding and manual testing. |
| **Testing** | `CONFIG_ENVIRONMENT=testing uv run pytest` | Used automatically by the test suite. |
| **Docker** | `CONFIG_ENVIRONMENT=docker uv run python main.py` | Used when running inside a container. |

---

## 🛠️ Operations & Features

### Real-Time Status Monitoring

The Orchestrator publishes every step change to the `orchestrator.status` topic. You can watch a workflow live using the manual test script:

```bash
# Requires dev dependencies: uv sync --extra dev
uv run python scripts/test_workflow.py --url https://arachne.test.dainst.org/entity/2003166

# Override Kafka broker (default: localhost:29092)
uv run python scripts/test_workflow.py \
  --url https://arachne.test.dainst.org/entity/2003166 \
  --kafka-broker localhost:29092 \
  --timeout 600

# Specify a workflow explicitly
uv run python scripts/test_workflow.py \
  --url https://example.com \
  --workflow standard_archive_workflow
```

The script requires a running Kafka broker and a running Orchestrator instance (`uv run python main.py`).

### Automated Background Tasks

The application includes a self-healing background task that runs every 30 seconds to:

1. **Timeout Monitoring**: Automatically fails workflows if a microservice (like the Archive Generator) stops responding.
2. **Memory Cleanup**: Removes old workflow data from the internal state to keep the system running fast.

---

## 🧪 Testing Guide

**All tests require dev dependencies:**

```bash
uv sync --extra dev
```

We use a three-tier testing strategy to ensure reliability.

### 1. Unit Tests (Fast, no Kafka)

Verifies pure business logic in isolation.

```bash
uv run pytest tests/unit/ -v
```

### 2. Integration Tests (Workflow logic, auto-starts Kafka via Docker)

Tests the full orchestration flow. Kafka is started automatically via `docker compose` if `AUTO_START_KAFKA=true` (the default).

```bash
uv run pytest tests/integration/ -v

# Disable automatic Kafka startup (if you already have Kafka running):
AUTO_START_KAFKA=false uv run pytest tests/integration/ -v
```

### 3. End-to-End Tests (Full ecosystem, requires Docker)

Spins up the entire stack including mock microservices.

```bash
uv run pytest tests/e2e/ -v
```

### 4. Manual Smoke Test Script

Use `scripts/test_workflow.py` to fire a real request at a running Orchestrator and watch it progress step-by-step.

**Prerequisites:** Kafka running, Orchestrator running (`uv run python main.py`).

```bash
# Start infrastructure
docker compose up -d kafka kafka-ui

# Start orchestrator (in a separate terminal)
uv run python main.py

# Run the smoke test
uv run python scripts/test_workflow.py --url https://arachne.test.dainst.org/entity/2003166
```

---

## 📖 Deep Dives

For detailed technical technical explanations of each module, check the dedicated READMEs:

* [**Configs**](./configs/README.md) - How to manage environment variables and YAML settings.
* [**Orchestration Logic**](./orchestration_services/README.md) - How the state machine and workflows work.
* [**Kafka Transport**](./transport_services/README.md) - Topic names, event models, and message handling.
* [**Utility Scripts**](./scripts/README.md) - Detailed guide for the manual test script.
* [**Full Testing Guide**](./tests/README.md) - Deep dive into fixtures and mocking.

---
