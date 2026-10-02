# CIVERS

CIVERS captures web pages, stores each saved version as a **snapshot**, and can extract structured metadata from the captured HTML.

## Quick start

Install [Docker with Compose](https://docs.docker.com/engine/install/), clone the repository, and run these commands from its root folder:

```sh
git clone https://github.com/dainst/civers.git
cd civers
mkdir -p .browsertrix-jobs
docker compose --profile browsertrix up -d --build --wait
```

Docker builds and starts all four applications, Kafka, Kafka UI and Browsertrix. The first build can take several minutes.

Open <http://localhost:8000>. Select a configured website, enter a page URL and start a capture. Open the completed request to view or download its files.

| Action | Command |
| --- | --- |
| Show containers | `docker compose --profile browsertrix ps` |
| Follow logs | `docker compose --profile browsertrix logs -f` |
| Stop containers; keep saved data | `docker compose --profile browsertrix down` |

## How it works

1. Web Interface receive the request and sends it to Orchestrator through Kafka.
2. Orchestrator selects the website's workflow and sends a capture job to Archive Generator.
3. Archive Generator captures the page, uploads files to Web Interface by HTTP, and reports the result through Kafka.
4. If the workflow includes metadata, Orchestrator sends Metadata Extractor the saved HTML's download URL. It extracts metadata and stores the configured outputs.
5. Orchestrator sends progress and final status to Web Interface by HTTP.

Kafka carries jobs and results; HTTP carries files and web status updates. The request ID connects the jobs and status messages. A snapshot ID identifies one saved capture. A workflow can capture only or capture and then extract metadata.

## Components

| Component | Owns |
| --- | --- |
| [Web Interface](civers_archive_web_interface/README.md) | Requests, status, saved files and browsing |
| [Orchestrator](civers_orchestrator/README.md) | Workflow selection, step order, results and timeouts |
| [Archive Generator](civers_archive_generator/README.md) | Browser capture and generated files |
| [Metadata Extractor](civers_metadata_extractor/README.md) | JSON, JSON-LD and CSS extraction with metadata validation |
| [civers_common](civers_common/README.md) | Shared configuration, request dispatch and communication code |
| [Change Detection](civers_change_detection/README.md) | under construction |
| PID Generation and url resoultion | plannned |

### Generated Artifacts

| Artifact | Description |
| --- | --- |
| `archive.wacz` | Web archive for replay |
| `screenshot.png` | Full-page screenshot |
| `singlefile.html` | Self-contained HTML snapshot |
| `dom-snapshot.html` | Raw DOM snapshot |
| `metadata.json` | Extracted metadata (DataCite format) |

## Configuration

YAML files live under `configs/data/<component>/`. Defaults are combined with one selected environment. Edit the YAML files to change settings, then restart the affected services. See [Configuration](configs/README.md) for defaults and environment overrides.

## License

### Third-Party Tools

CIVERS integrates the following open-source tools:

| Tool | License | Purpose |
| --- | --- | --- |
| [Scoop](https://github.com/harvard-lil/scoop) | MIT | Web archiving (Harvard Library Innovation Lab) |
| [SingleFile](https://github.com/nicholasaleks/single-file-cli) | AGPL-3.0 | Self-contained HTML snapshots |
| [ReplayWeb.page](https://replayweb.page/) | AGPL-3.0 | WACZ archive replay |
| [Apache Kafka](https://kafka.apache.org/) | Apache-2.0 | Message streaming |
| [Browsertrix](https://github.com/webrecorder/browsertrix/tree/main) | AGPLv3 License | Web archiving |

Apache 2.0. See [LICENSE](LICENSE).