# Configuration Reference — `civers_common` (Generic / Shared)

This is the **canonical** documentation for the shared CiVers configuration system.
Every service builds on the base classes, the loader, and the exception defined here.

> Service-specific config docs (e.g. `civers_change_detection/configs/configs.md`) document
> **only** what that service adds or overrides. They link back to this file for everything
> generic — they must not repeat the content below.

---

## What lives here

```text
civers_common/src/civers_common/configs/
├── configs.md      # This generic documentation
├── __init__.py     # Re-exports the public config API
├── models.py       # Base Pydantic models + DomainResolutionMixin
├── loaders.py      # BaseYamlConfigLoader (hierarchical YAML loading)
└── exceptions.py   # ConfigurationError
```

Public API (import from the package root):

```python
from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseKafkaConfig,
    BaseStorageConfig,
    BaseTransportConfig,
    DomainResolutionMixin,
    BaseYamlConfigLoader,
    ConfigurationError,
)
```

---

## Architecture: hierarchical, environment-aware loading

The loader merges YAML files in this order (later overrides earlier):

1. `data/defaults/*.yaml` — base settings, merged alphabetically
2. `data/environments/<environment>.yaml` — environment-specific overrides
3. `${VAR:-default}` placeholders are expanded from environment variables
4. The merged dict is validated by a service's `ConfigDataModel` (Pydantic)

### Environment detection (priority order)

1. `CONFIG_ENVIRONMENT` env var
2. Docker — presence of `/.dockerenv` → `docker`
3. Pytest — presence of `PYTEST_CURRENT_TEST` → `testing`
4. Fallback → `development`

### Environment variable expansion

Any string value supports `${ENV_VAR:-default}`:
- If `ENV_VAR` is set, its value is used.
- Else the `default` (after `:-`) is used.
- Else the literal `${...}` is left untouched.

### Design principles

- **Type safety** — Pydantic V2 validates the final config.
- **Separation of concerns** — data (YAML) is separate from code (Python).
- **`extra="ignore"`** — all base models ignore unknown keys, so a service can keep
  fields in its YAML that other services don't model.

---

## Base Models (`models.py`)

All base models set `model_config = ConfigDict(extra="ignore")`.

### `BaseDomainConfig`

A single domain entry. Services extend it (CD adds `change_detection`, AG adds `generators`,
ME adds `input_source`/`extractor`/`mappings`, ORCH adds `workflow`, AWI adds `display_name`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *required* | FQDN, wildcard (`*.example.org`), local hostname, or `"default"` |
| `enabled` | `bool` | `True` | Whether this domain is active |
| `description` | `str` | `""` | Human-readable description |
| `webpage_types` | `"dynamic"` \| `"static"` | `"dynamic"` | Shared page-type marker |

- Validator `validate_domain_name` enforces the `name` format.
- Properties: `is_wildcard` (`*` in name), `is_default` (name == `"default"`).

### `BaseKafkaConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bootstrap_servers` | `str` | *required* | Non-empty; trimmed |
| `topics` | `dict[str, str]` | *required* | At least one topic |
| `consumer_group` | `str` | `"civers_default_group"` | Override per service |
| `consumer` | `dict \| None` | `None` | Raw consumer settings |

- Validators: `validate_bootstrap_servers` (non-empty), `validate_topics` (≥1).
- `sync_consumer_group` copies `consumer["group_id"]` into `consumer_group` when present.

### `BaseTransportConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `list[str]` | *required* | ≥1 transport |
| `kafka` | `BaseKafkaConfig \| None` | `None` | Required when `"kafka"` is in `enabled` |

- Validators: `validate_enabled` (≥1), `validate_enabled_have_config` (every enabled
  transport must be supported and configured).

### `BaseStorageConfig`

Multi-backend storage (used by AG, ME; not by CD or AWI).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `list[str] \| None` | `None` | Multi-backend mode |
| `backend` | `str` | `"local_file"` | Legacy single-backend mode |
| `backends` | `dict[str, dict]` | `{"local_file": {"base_path": "archives"}}` | Per-backend config |

- Methods: `get_enabled_backends()`, `get_backend_config(backend=None)`.
- Validators: `validate_enabled_backends` (non-empty if provided),
  `validate_enabled_backends_exist` (every enabled backend has config).

### `BaseAppConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `"civers_service"` | Service name |
| `version` | `str` | `"1.0.0"` | Service version |
| `environment` | `str` | `"development"` | Active environment |
| `transport` | `BaseTransportConfig \| None` | `None` | Transport settings |

- Method: `get_kafka_config()` → `transport.kafka` (or `None`).

---

## `DomainResolutionMixin`

Mix into a service's root `ConfigDataModel` to get standardized domain lookup.
The consuming class must expose `self.domains: list[BaseDomainConfig]`.

| Method | Description |
|--------|-------------|
| `normalize_hostname(hostname)` | Lowercase, strip, drop port (static) |
| `resolve_domain(identifier)` | Resolve by hostname/domain name |
| `resolve_domain_for_url(url)` | Parse URL → hostname → `resolve_domain` |

**Resolution order:** exact match → wildcard (`*.example.org` matches `sub.example.org`)
→ `default` entry → raise `ConfigurationError`. A matched-but-disabled domain also raises.

---

## `BaseYamlConfigLoader` (`loaders.py`)

Implements the hierarchical loading described above. It returns a **raw dict**; each service
subclasses it to validate that dict into its own `ConfigDataModel`.

| Member | Purpose |
|--------|---------|
| `__init__(config_dir=None, environment=None)` | `config_dir` falls back to `CONFIG_DIR` env, then `_default_config_dir()` |
| `_default_config_dir()` | **Override** in a subclass to point at the service's `configs/data` |
| `_detect_environment()` | Environment detection (see above) |
| `load_raw()` | Load defaults + env overrides, deep-merge, expand env vars → `dict` |

Helpers (`_deep_merge`, `_load_yaml_file`, `_expand_env_vars`) are shared and rarely overridden.

---

## `ConfigurationError` (`exceptions.py`)

The canonical exception for all config errors and failed lookups across CiVers. Services may
subclass it if they need a finer-grained hierarchy.

---

## How a service extends this

1. Add the dependency:
   ```toml
   # pyproject.toml
   dependencies = ["civers-common", ...]

   [tool.uv.sources]
   civers-common = { workspace = true }
   ```
2. Subclass the base models, adding only service-specific fields/overrides:
   ```python
   from civers_common import BaseAppConfig, BaseDomainConfig, DomainResolutionMixin

   class DomainConfig(BaseDomainConfig):
       my_field: MyServiceConfig = Field(default_factory=MyServiceConfig)

   class ConfigDataModel(DomainResolutionMixin, BaseModel):
       app: AppConfig
       domains: list[DomainConfig] = Field(default_factory=list)
   ```
3. Subclass the loader to bind the service's data dir + return the service model:
   ```python
   from pathlib import Path
   from civers_common import BaseYamlConfigLoader

   class YamlFileConfigLoader(BaseYamlConfigLoader):
       def _default_config_dir(self) -> Path:
           return Path(__file__).resolve().parent / "data"

       def load(self) -> ConfigDataModel:
           return ConfigDataModel(**self.load_raw())
   ```

See `civers_common/README.md` for packaging/`src`-layout details.
