# Configuration Reference — CiVers Change Detection

> **This document covers only what Change Detection (CD) adds on top of the shared
> configuration system.** For the generic architecture — hierarchical loading, environment
> detection, `${VAR:-default}` expansion, the base models (`BaseDomainConfig`,
> `BaseKafkaConfig`, `BaseTransportConfig`, `BaseAppConfig`), `DomainResolutionMixin`,
> `BaseYamlConfigLoader`, and `ConfigurationError` — see the canonical reference:
> [`civers_common` configs.md](../../civers_common/src/civers_common/configs/configs.md).

CD consumes `civers_common` and follows the shared defaults. The **only** CD-specific config
class is `ChangeDetectionStrategyConfig`; everything else is a thin subclass of a base model.

---

## CD config layout

```text
civers_change_detection/configs/
├── configs.md          # This document (CD-specific extension)
├── __init__.py         # Public API exports
├── models.py           # CD models (subclass civers_common bases)
├── loaders.py          # YamlFileConfigLoader(BaseYamlConfigLoader)
├── logging_config.py   # CD logging setup
└── data/
    ├── defaults/        # app.yaml, kafka.yaml, domains.yaml
    └── environments/    # testing / development / docker / production .yaml
```

`loaders.py` is a thin subclass of `BaseYamlConfigLoader`: it only overrides
`_default_config_dir()` (to point at `configs/data`) and adds `load() -> ConfigDataModel`.

| File | Purpose |
|------|---------|
| `data/defaults/app.yaml` | App metadata + transport defaults |
| `data/defaults/kafka.yaml` | Kafka connection defaults (under `app.transport.kafka`) |
| `data/defaults/domains.yaml` | Per-domain change detection configuration |
| `data/environments/*.yaml` | Environment-specific overrides |

---

## `ChangeDetectionStrategyConfig` (CD-specific)

Per-domain change detection settings, nested under `change_detection` in each domain entry.
This is the one class that is unique to CD.

### Fields

| Field | Type | Default | When enforced | Description |
|-------|------|---------|---------------|-------------|
| `detection_strategy` | `"css_selector"` | `"css_selector"` | Always | Strategy used to fetch/extract content |
| `comparison_algorithm` | `"simple_text"` \| `"simhash"` | `"simple_text"` | Always | Algorithm for comparing versions |
| `rendering_engine` | `"httpx"` \| `"playwright"` | `"httpx"` | Always | HTTP client for fetching pages |
| `css_selectors` | `list[str]` | `["body"]` | When `detection_strategy == "css_selector"` (must be non-empty, no blank entries) | CSS selectors to extract text from |
| `simhash_threshold` | `int` | `3` | Range 0–64 only when `comparison_algorithm == "simhash"` | Hamming-distance threshold for SimHash |
| `archive_interval` | `str \| None` | `None` | Optional | Cooldown before re-checking a URL (see below) |
| `request_timeout_seconds` | `int` (≥1) | `30` | Always | HTTP request timeout in seconds |

### Conditional validation

- **`css_selectors`** — validated only for the `css_selector` strategy: must be a non-empty
  list with no blank entries; whitespace is stripped automatically.
- **`simhash_threshold`** — the 0–64 range is enforced only when using `simhash`; any value is
  accepted with `simple_text`.

### Archive interval format

Duration string `<number><unit>`:

| Unit | Meaning | Example | Seconds |
|------|---------|---------|---------|
| `h` | Hours | `6h` | 21,600 |
| `d` | Days | `7d` | 604,800 |
| `w` | Weeks | `2w` | 1,209,600 |
| `m` | Months (30 days) | `1m` | 2,592,000 |

If unset (`None`), the interval check is skipped and every request triggers change detection.
Call `get_archive_interval_seconds()` to parse the string to seconds programmatically.

### Strategy / algorithm naming convention

Names resolve to classes automatically, so adding a new one is config + a matching module:

**Detection strategies** (`DetectionStrategyName` Literal in `models.py`):

| Config value | Class | Module |
|--------------|-------|--------|
| `css_selector` | `CssSelectorDetectionStrategy` | `change_detection_services/strategies/css_selector_strategy.py` |

> Add another by extending the Literal and creating `{name}_strategy.py` → `{PascalCase}DetectionStrategy`.

**Comparison algorithms** (`ComparisonAlgorithmName` Literal in `models.py`):

| Config value | Class | Module |
|--------------|-------|--------|
| `simple_text` | `SimpleTextComparison` | `change_detection_services/comparison/simple_text_comparison.py` |
| `simhash` | `SimHashComparison` | `change_detection_services/comparison/simhash_comparison.py` |

> Add another by extending the Literal and creating `{name}_comparison.py` → `{PascalCase}Comparison`.

---

## CD subclasses of the shared models

These add nothing beyond what's noted; all other fields/validators/behavior come from the base
classes documented in the [`civers_common` reference](../../civers_common/src/civers_common/configs/configs.md).

| CD class | Base | CD-specific addition / override |
|----------|------|----------------------------------|
| `DomainConfig` | `BaseDomainConfig` | adds `change_detection: ChangeDetectionStrategyConfig` |
| `KafkaConfig` | `BaseKafkaConfig` | `consumer_group` default → `"change_detection_group"` |
| `TransportConfig` | `BaseTransportConfig` | `kafka` typed as CD `KafkaConfig` |
| `AppConfig` | `BaseAppConfig` | `name` → `"change_detection_system"`, `version` → `"0.1.0"`, `transport` typed as CD `TransportConfig` |
| `ConfigDataModel` | `DomainResolutionMixin` + `BaseModel` | holds `app`, `transport`, `domains`; keeps a local `sync_transport` (root ↔ `app.transport`) pending the Kafka/Transport unification plan |

> Domain lookup uses the inherited `resolve_domain` / `resolve_domain_for_url`.
> `webpage_types` is inherited from `BaseDomainConfig` (optional, default `"dynamic"`).

---

## Example domain configuration

```yaml
domains:
  - name: arachne.dainst.org
    enabled: true
    change_detection:
      detection_strategy: css_selector
      comparison_algorithm: simhash
      css_selectors:
        - "div.content-page"
      simhash_threshold: 3
      archive_interval: "1m"

  - name: publications.dainst.org
    enabled: true
    change_detection:
      detection_strategy: css_selector
      comparison_algorithm: simple_text
      css_selectors:
        - "article.content"
        - "div.main-text"
      rendering_engine: playwright    # JS-heavy page
      archive_interval: "7d"

  - name: default
    enabled: true
    change_detection:
      detection_strategy: css_selector
      comparison_algorithm: simple_text
      # No archive_interval → every request triggers a check
```

---

## Logging
TODO: To be moved to civers_common
CD provides its own logging setup in `configs/logging_config.py`:

```python
import logging
from configs.logging_config import setup_logging, get_logger

setup_logging(level=logging.INFO, suppress_kafka_logs=True)
logger = get_logger("my_component")
```

- `setup_logging()` configures the root logger, optionally adds a file handler, and suppresses
  noisy Kafka/urllib3 loggers.
- `get_logger(name)` returns a named `logging.Logger`.
