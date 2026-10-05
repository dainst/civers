# Archive Generator tests

## Run

From the repository root:

```sh
CONFIG_ENVIRONMENT=testing uv run --no-sync --directory civers_archive_generator python -m pytest tests/unit/
```

For one test file, run from the component directory:

```sh
cd civers_archive_generator
CONFIG_ENVIRONMENT=testing uv run --no-sync python -m pytest tests/unit/archive_generators/test_browsertrix.py
```

## Coverage

Unit tests cover configuration, URL matching, artifact selection, capture adapters,
storage publication, command dispatch and process shutdown. Browsertrix tests use
synthetic WACZ files and isolated subprocesses; they do not run a real browser.

The test folders follow the service boundaries:

| Folder | Behavior covered |
| --- | --- |
| `unit/configs` | Archive-specific validation and the shared YAML catalog |
| `unit/domain` | Immutable commands, artifact files and archive bundles |
| `unit/archive_generators` | Factory/config pairing, adapter outputs and subprocess cleanup |
| `unit/services` | `execute(ArchiveCommand)`, result states, workspace inventory, metadata and URL guard |
| `unit/storage_layer` | Backend registration, concurrent publication and upload selection |
| `unit/transport_services` | CLI, REST and Kafka conversion to commands and results |
| `unit/test_main.py`, `unit/test_process_lifecycle.py` | Composition, shutdown and process exit |

Service workflow tests create synthetic artifact files and use the real workspace,
runner and metadata writer. Browser capture, DNS and remote publication are replaced
at their boundaries. Complete, partial and failed results are checked through
`execute()`, the archive service interface contract.

Shared configuration helpers, client options, message acknowledgement and dead-letter
behavior are tested by `uv run --no-sync --directory civers_common python -m pytest`.
Component tests retain archive-specific policy and adapter wiring.

Coverage reporting is optional; normal runs do not require the removed `.coveragerc`.
From the component directory, with the dev dependencies installed:

```sh
uv run --no-sync python -m pytest tests/unit/ \
  --cov=archive_generators --cov=archive_services --cov=domain \
  --cov=storage_layer --cov=transport_services --cov=configs --cov=main \
  --cov-report=term-missing
```

## Kafka integration

With a local broker already running, use the component directory:

```sh
AUTO_START_KAFKA=false KAFKA_BOOTSTRAP_SERVERS=localhost:29092 \
  uv run --no-sync python -m pytest tests/integration/test_kafka_flow.py --run-integration -q
```

The four cases check complete, failed, invalid and unroutable requests. Each uses
unique topics and consumer groups, real Kafka clients and a substitute capture
handler. Each case checks receipt of the result or dead-letter message and eventual
commit of the source offset. Test topics are removed afterwards.

Kafka broker fixtures live under `integration/conftest.py`; they are not loaded by a
unit-only run. Integration tests are skipped unless `--run-integration` is supplied.

The broker must allow topic creation and deletion. A missing broker causes a skip,
not a pass. With `AUTO_START_KAFKA=true`, the fixture can start local Docker Kafka.
These tests do not verify browser capture or Web Interface publication.

## Manual checks

Follow the [AG walkthrough](../../docs/manual-review/archive-generator.md) for real
captures, output files, uploads, redirects and cleanup. Recheck captures when
changing the pinned Browsertrix version or its output handling.
