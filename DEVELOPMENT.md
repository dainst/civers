# CIVERS Development and Deployment Guide

This guide details the standardized workflows for setting up, running, testing, and debugging the CIVERS full-stack repository.

---

## 1. Prerequisites & Host Setup

CIVERS supports two execution models: **Docker Compose** (for isolated, containerized execution) and **Host-Local** (for fast feature development and headed browser debugging).

### Host-Local Requirements (Ubuntu)
The repository uses `uv` for Python package management and local virtual environment configurations, and contains a Node.js-based archiving package.

To configure your host machine automatically:
```bash
make setup_host
```

**What the setup script does:**
1. Validates host system dependencies (`python3`, `uv`, `node`, `npm`, and `docker`).
2. Runs `uv sync` at the workspace root to build and link the shared virtual environment (`.venv/`) for all Python services.
3. Installs Playwright Chromium browser binaries for the Python runtime.
4. Installs local npm dependencies and Playwright Chromium inside `civers_archive_generator/lib/scoop/`.
5. Fixes executable permissions for the SingleFile Linux binary.
6. Creates local output storage folders (`civers_archive_generator/archives`).

---

## 2. Running CIVERS

All execution and control flows are managed via the root [Makefile](Makefile).

### Option A: Host-Local Run (Recommended for Active Development)
Starts the Kafka infrastructure broker in Docker, and runs all Python microservices natively on the host (with instant reloading, fast compilation, and headed browser support).

* **One-Step Setup and Run:**
  ```bash
  make run_host
  ```
* **Daily Start (Skipping dependency installation):**
  ```bash
  make dev-host
  ```
* **Visual Browser Debugging (Headed Mode):**
  By default, browser capturing is headless. To open a physical Chromium window during archiving to watch interactions:
  ```bash
  SCOOP_HEADLESS=false make dev-host
  ```

### Option B: Containerized Run (Recommended for Integration Testing)
Launches the entire full-stack inside Docker containers.
* **Start Container Stack:**
  ```bash
  make dev
  ```
* **Follow Container Logs:**
  ```bash
  make logs
  ```
* **Clean Stop & Remove Containers:**
  ```bash
  make stop
  ```
* **Rebuild Image Cache:**
  ```bash
  make rebuild
  ```

### Service-Specific Control
You can start or stop individual Docker containers using the symmetric targets.
Acronyms/Identifiers: `web`, `ag`, `orch`, `me`, `cd`, `kafka`, `kafka-ui`

* **Start Service Container:**
  ```bash
  make <service>-start     # e.g., make web-start, make cd-start, make kafka-start
  ```
* **Stop Service Container:**
  ```bash
  make <service>-stop      # e.g., make web-stop, make cd-stop, make kafka-stop
  ```

### Status Inventory
To inspect running container services, active configurations, and Kafka endpoints:
```bash
make status
# OR
make ps
```

---

## 3. Testing and Verification

### Live Storage End-to-End Verification
To verify that the database, REST API, and file storage systems are active and accepting uploads, run the storage verification checks:
* **Passive Checks (Health status only):**
  ```bash
  make verify-storage
  ```
* **Active Checks (Performs mock multipart uploads and download retrieval verification):**
  ```bash
  make verify-storage UPLOAD=true
  ```

### Running Unit Tests
* Run **all** services' unit tests (no Kafka/broker required):
  ```bash
  make test
  ```
* Run a **single** service's unit tests (`orch`, `ag`, `me`, `awi`, `cd`, `common`):
  ```bash
  make orch-test        # or ag-test / me-test / awi-test / cd-test / common-test
  ```
  Each target uses that service's correct unit command (dir- or marker-scoped) so integration
  tests requiring a broker are excluded.

### Running the Smoke (End-to-End) Test
Exercises the whole pipeline (Web Interface → Orchestrator → Archive Generator → Metadata
Extractor → Web Interface) against a **running** stack — start it first with `make dev`.
```bash
make smoke                                   # default test URL
make smoke URL="https://example.com"         # custom URL
make smoke ARGS="--timeout 300 --web-url http://localhost:8000"
```

### Running Integration Tests
Integration tests are excluded from `make test`; run them per service (they may need Kafka):
```bash
cd civers_archive_generator && uv run pytest tests/integration/ --run-integration
cd civers_orchestrator && uv run pytest tests/integration/     # auto-starts Kafka via Docker
```

### CLI Direct Archiving
To run the Archive Generator directly from the command line for a single URL without using Kafka queues:
```bash
make ag-run-direct URL="https://example.com"
```

---

## 4. Debugging with VS Code

### Debugging in Host-Local Mode (`make dev-host`)

#### Method A: Compound Debugger Launch (Recommended)
You can let VS Code launch all microservices in the editor with debuggers attached from startup.

1. Create a [launch.json](.vscode/launch.json) file at `.vscode/launch.json`:
   ```json
   {
       "version": "0.2.0",
       "configurations": [
           {
               "name": "Service: Web Interface",
               "type": "python",
               "request": "launch",
               "module": "uvicorn",
               "cwd": "${workspaceFolder}/civers_archive_web_interface",
               "args": ["app.main:app", "--host", "0.0.0.0", "--port", "8000"],
               "env": {
                   "CONFIG_ENVIRONMENT": "development",
                   "CONFIG_DIR": "${workspaceFolder}/configs",
                   "KAFKA_BOOTSTRAP_SERVERS": "localhost:29092"
               },
               "console": "integratedTerminal"
           },
           {
               "name": "Service: Orchestrator",
               "type": "python",
               "request": "launch",
               "program": "main.py",
               "cwd": "${workspaceFolder}/civers_orchestrator",
               "env": {
                   "CONFIG_ENVIRONMENT": "development",
                   "CONFIG_DIR": "${workspaceFolder}/configs",
                   "KAFKA_BOOTSTRAP_SERVERS": "localhost:29092"
               },
               "console": "integratedTerminal"
           },
           {
               "name": "Service: Archive Generator",
               "type": "python",
               "request": "launch",
               "program": "main.py",
               "cwd": "${workspaceFolder}/civers_archive_generator",
               "env": {
                   "CONFIG_ENVIRONMENT": "development",
                   "CONFIG_DIR": "${workspaceFolder}/configs",
                   "KAFKA_BOOTSTRAP_SERVERS": "localhost:29092"
               },
               "console": "integratedTerminal"
           },
           {
               "name": "Service: Metadata Extractor",
               "type": "python",
               "request": "launch",
               "program": "main.py",
               "cwd": "${workspaceFolder}/civers_metadata_extractor",
               "env": {
                   "CONFIG_ENVIRONMENT": "development",
                   "CONFIG_DIR": "${workspaceFolder}/configs",
                   "KAFKA_BOOTSTRAP_SERVERS": "localhost:29092"
               },
               "console": "integratedTerminal"
           }
       ],
       "compounds": [
           {
               "name": "Debug All Services (Host)",
               "configurations": [
                   "Service: Web Interface",
                   "Service: Orchestrator",
                   "Service: Archive Generator",
                   "Service: Metadata Extractor"
               ]
           }
       ]
   }
   ```
2. Start the Kafka backend: `make kafka-start`
3. Go to VS Code **Run & Debug** (`Ctrl+Shift+D`), select **Debug All Services (Host)**, and press `F5`.

#### Method B: Attach to Process
1. Start the stack: `make dev-host`
2. Add a basic attach configuration to your `.vscode/launch.json`:
   ```json
   {
       "name": "Python: Attach to Process",
       "type": "python",
       "request": "attach",
       "processId": "${command:pickProcess}"
   }
   ```
3. Press `F5`, search/select the service process (e.g., `uvicorn` or `orchestrator`), and debug.
