# Archive Generator inputs and outputs

| Adapter | Input |
| --- | --- |
| `ArchiveKafkaTransport` | Archive request events from Kafka |
| `ArchiveRestTransport` | HTTP `POST /archive` |
| `ArchiveCliTransport` | Command-line arguments |

Each adapter converts input into `ArchiveCommand` and sends it through
`CommandBus` to `ArchiveService.execute`. It converts the returned `Result`
into a Kafka event, HTTP response or CLI output.

Shared code manages Kafka clients, HTTP serving, CLI execution and shutdown.
See [request handling](../../civers_common/docs/transport.md) and
[Archive Generator](../README.md).
