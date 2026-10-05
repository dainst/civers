# Archive Generator

Archive Generator turns a page URL into capture files: web archives, screenshots, HTML snapshots or a self-contained HTML page. Website rules choose the tools and outputs.

## Request flow

1. Kafka, HTTP or CLI input becomes an `ArchiveCommand` containing a URL and request ID.
2. `ArchiveService.execute` resolves the website rule and creates a snapshot directory.
3. The configured generators run and report which files succeeded or failed.
4. AG writes capture generator metadata and publishes files to the selected storage destinations.
5. The caller receives the snapshot ID, output paths and complete, partial or failed status.

Scoop and SingleFile run beside AG. Browsertrix runs in a separate container and exchanges jobs through a shared directory. Upload failures leave local files available and do not by themselves make the capture result fail.

## Code

| Location | Responsibility |
| --- | --- |
| [main.py](main.py) | Load settings,archive service handle, transports service  |
| [transport_services/](transport_services/README.md) | Convert Kafka, HTTP and CLI inputs into commands |
| [archive_services/](archive_services/README.md) | Coordinate captures, output files and results |
| [archive_generators/](archive_generators/) | Implement each capture tool |
| [storage_layer/](storage_layer/) | Write or upload completed files |

