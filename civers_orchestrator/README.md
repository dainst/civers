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

* **Python 3.11+**
* **[uv](https://github.com/astral-sh/uv)**: A fast Python package manager.
* **Docker**: To run the Kafka messenger locally.

### 1. Basic Setup

```bash
# 1. Install all dependencies
uv sync

# 2. Start the messenger (Kafka) 
docker compose up -d kafka kafka-ui
```

### 2. Running the Application

| Environment | Command | Use Case |
| :--- | :--- | :--- |
| **Development** | `CONFIG_ENVIRONMENT=development uv run python main.py` | Default for local coding and manual testing. |
| **Testing** | `CONFIG_ENVIRONMENT=testing uv run pytest` | Used automatically by the test suite. |
| **Docker** | `CONFIG_ENVIRONMENT=docker uv run python main.py` | Used when running inside a container. |

---

## 🛠️ Operations & Features

### Real-Time Status Monitoring

The Orchestrator now publishes every step change to the `orchestrator.status` topic. You can "watch" a workflow live using our utility script:

```bash
uv run python scripts/test_workflow.py --url https://arachne.test.dainst.org/entity/2003166
```

*Note: This script provides a "Live Dashboard" view of the Kafka traffic.*

### Automated Background Tasks

The application includes a self-healing background task that runs every 30 seconds to:

1. **Timeout Monitoring**: Automatically fails workflows if a microservice (like the Archive Generator) stops responding.
2. **Memory Cleanup**: Removes old workflow data from the internal state to keep the system running fast.

---

## 🧪 Testing Guide

We use a three-tier testing strategy to ensure reliability.

### 1. Logic Tests (Fast)

Verifies the internal "Brain" without needing Kafka.

```bash
uv run pytest tests/unit/        # Smallest components
uv run pytest tests/integration/ # Workflow logic
```

### 2. End-to-End Tests (Complete)

Simulates the entire ecosystem. **Requires Docker/Kafka.**

```bash
uv run pytest tests/e2e/ -v
```

### 3. Manual Smoke Testing

Use the development script to verify plumbing against real infrastructure.

```bash
uv run python scripts/test_workflow.py --url [YOUR_URL]
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
