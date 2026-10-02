# Running CiVers Locally with Kafka

This guide explains how to run the CiVers services on your host machine, with Kafka and the Browsertrix worker running in Docker. It covers starting the services, submitting requests, viewing results, and monitoring the Kafka message flow.

## 1. Prepare the development environment

### Environment versions

The following versions were recorded for this development setup:

| Component | Version |
| --- | --- |
| Ubuntu | 26.04.1 LTS |
| Docker | 28.3.3 |
| Docker Compose | v2.39.1 |
| Python | 3.12 |
| Node.js | 22 |

### Shared prerequisites

Install the following tools before starting:

- [Docker Engine with Docker Compose](https://docs.docker.com/engine/install/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for managing Python dependencies and running the services

Run all commands from the project root unless a step explicitly changes directories. Open a separate terminal for each long-running service, and keep those terminals open while testing. Use an additional terminal to submit requests.

Start Kafka:

```bash
docker compose up -d kafka
```

Install the Python dependencies for all workspace packages and extras using the existing lockfile:

```bash
uv sync --locked --all-packages --all-extras
```

### Service overview

| Component | Abbreviation | Runs in | Purpose |
| --- | --- | --- | --- |
| Archive Web Interface | AWI | Host | Displays archive results and provides access to application configuration |
| Archive Generator | AG | Host | Generates archive artifacts using the configured capture tools |
| Metadata Extractor | ME | Host | Extracts metadata from supplied HTML or a downloadable HTML document |
| Orchestrator | ORCH | Host | Coordinates archive generation and metadata extraction according to the domain's workflow |
| Kafka | — | Docker | Carries messages between services |
| Browsertrix worker | — | Docker | Processes Browsertrix capture jobs |

The examples below use the project's development configuration. The capture tools and workflow used for each URL depend on its domain configuration.

## 2. Start the Archive Web Interface (AWI)

Start the AWI:

```bash
uv run --directory ./civers_archive_web_interface --no-sync \
  uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

- Open the web interface at [http://localhost:8000/](http://localhost:8000/).

The interface may initially contain no archives. Keep the AWI running so that the other services can upload their results to it.

## 3. Start and test the Archive Generator (AG)

### 3.1. Install the Scoop dependencies

This setup uses Scoop `0.7.0`, which requires Node.js 22 or newer and Playwright Chromium. The commands below assume that `nvm` is installed and that the checkout provides an `.nvmrc` file for `nvm use`.

From the project root, select the configured Node.js version, install Scoop's dependencies, and install Chromium:

```bash
nvm use

cd civers_archive_generator/lib/scoop
npm install
npx playwright install chromium
./bin/cli.js --version
```

The version command should report `0.7.0`.

Return to the project root:

```bash
cd ../../..
```

### 3.2. Start the Browsertrix worker

Create the shared jobs directory and start the Browsertrix container:

```bash
mkdir -p .browsertrix-jobs
docker compose --profile browsertrix up -d browsertrix
```

### 3.3. Start the Archive Generator

In a separate terminal at the project root, run:

```bash
CONFIG_ENVIRONMENT=development uv run python civers_archive_generator/main.py
```

Keep this service running while submitting the requests below.

### 3.4. Submit an archive request that uses Browsertrix and SingleFile

In another terminal, submit an archive request through Kafka:

```bash
uv run python scripts/send_message_to_kafka.py \
  --urls "https://viamus2.gbv.de/epochen/" \
  --request-type archive
```

In this development configuration, `viamus2.gbv.de` uses Browsertrix and SingleFile. The Archive Generator picks up the request and generates the artifacts.

After the request completes:

- Find the local artifacts in `civers_archive_generator/archives/viamus2_gbv_de/epochen/`.
- Open or refresh the [AWI](http://localhost:8000/). Under **Top archived domains**, select the **viamus2.gbv.de** card to inspect the uploaded archive.

### 3.5. Submit an archive request that uses Scoop

Submit a request for a domain configured to use Scoop:

```bash
uv run python scripts/send_message_to_kafka.py \
  --urls "https://sempub.ub.uni-heidelberg.de/propylaeum_vitae/wisski/navigate/12121/view" \
  --request-type archive
```

After the request completes:

- Find the local artifacts under `civers_archive_generator/archives/sempub_ub_uni_heidelberg_de/`.
- Open or refresh the [AWI](http://localhost:8000/). Under **Top archived domains**, select the **sempub.ub.uni-heidelberg.de** card to inspect the uploaded archive.

## 4. Start and test the Metadata Extractor (ME)

Use the [ME quick start](civers_metadata_extractor/README.md#quick-start) for
[CLI](civers_metadata_extractor/README.md#cli),
[REST](civers_metadata_extractor/README.md#rest-api), or
[Kafka](civers_metadata_extractor/README.md#kafka). All modes use
[`configs/data/metadata_extractor`](configs/data/metadata_extractor), with enabled
profiles for publications, viamus2, Field and Arachne. Local runs save under
`output/metadata`; configure `app.fetch_policy` before downloading sources.

ME requests use typed `input` for supplied content. The legacy
`send_message_to_kafka.py --html-content` example sends the removed `html_content`
field; use the request format in the ME guide. `arachne.test.dainst.org` remains
disabled and needs its own profile before that archive-and-metadata workflow can
complete. Arachne's enabled public-site profile requires rendered HTML.

## 5. Start and test the Orchestrator (ORCH)

Before testing the complete workflow, keep Kafka, the AWI, the Archive Generator, and the Metadata Extractor running. Keep the Browsertrix worker available for domains configured to use it.

In a separate terminal at the project root, start the Orchestrator:

```bash
CONFIG_ENVIRONMENT=development uv run python civers_orchestrator/main.py
```

In another terminal, submit an orchestration request:

```bash
uv run python scripts/send_message_to_kafka.py \
  --urls "https://arachne.test.dainst.org/entity/1215990" \
  --request-type orchestrator
```

The domain `arachne.test.dainst.org` is configured to use `archive_and_metadata_workflow`. Processing proceeds as follows:

1. The Orchestrator receives the request and publishes an archive-generation request to Kafka.
2. The Archive Generator picks up that request, generates the artifacts, and publishes an archive-completion message.
3. The Orchestrator receives the completion message and publishes a metadata-extraction request.
4. If the domain has an enabled ME profile, extraction runs and writes to its configured storage. The default disabled `arachne.test.dainst.org` profile produces an extraction failure until configured.

When processing finishes, open or refresh the [AWI](http://localhost:8000/) to inspect saved artifacts. Metadata is available only when ME has a working domain profile and upload storage configured.

## 6. Monitor the Kafka message flow

The Kafka flow monitor shows messages exchanged between the CiVers services. Use it to follow a request and compare the configured workflows.

With the services from the previous section still running, start the monitor in a new terminal:

```bash
uv run python scripts/kafka_flow_monitor.py
```

Keep this terminal visible while submitting the following requests from another terminal.

### 6.1. Observe archive generation with metadata extraction

```bash
uv run python scripts/send_message_to_kafka.py \
  --urls "https://arachne.test.dainst.org/entity/1215990" \
  --request-type orchestrator
```

Watch the monitor output for messages involving **ORCH**, **AG**, and **ME**. This domain uses the workflow that performs both archive generation and metadata extraction.

### 6.2. Observe archive generation only

```bash
uv run python scripts/send_message_to_kafka.py \
  --urls "https://viamus.uni-goettingen.de/fr/sammlung/ab_rundgang/q" \
  --request-type orchestrator
```

For this request, watch for messages involving **ORCH** and **AG**. The domain is configured for archive generation only, so the Orchestrator does not request metadata extraction.

### Workflow comparison

| Domain | Configured `workflow_name` | Services involved in the Kafka workflow |
| --- | --- | --- |
| `arachne.test.dainst.org` | `archive_and_metadata_workflow` | ORCH, AG, ME |
| `viamus.uni-goettingen.de` | `archive_generation_only_workflow` | ORCH, AG |

Both examples make their results available through the AWI. The table lists the services participating in the Kafka workflow; the AWI is used to view the uploaded results.

### 7 Adding new domain for archiving