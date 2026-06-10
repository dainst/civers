# civers_common

The shared internal library for the CiVers platform. It is the single home for code that is
common across the CiVers microservices (Orchestrator, Archive Generator, Metadata Extractor,
Archive Web Interface, Change Detection).

Instead of each service maintaining its own copy of the same logic, the shared pieces live
here once and every service imports them. A fix or improvement is then a single change in one
place rather than the same edit repeated across five repositories' worth of code.

> Scope: `civers_common` is for **genuinely shared** logic — code used (in production) by two
> or more services. Configuration
> is the first area that has been consolidated; more cross-cutting concerns (e.g. transport /
> Kafka logic, shared event models, common utilities) are expected to move here over time.

---

## What's in it today

| Module | What it provides |
|---|---|
| `civers_common.configs` | Pydantic v2 base config models, a domain-resolution mixin, a hierarchical YAML loader, and a shared `ConfigurationError`. |

The public API is re-exported from the top-level package:

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

As more shared logic lands, it will be added as new modules under `civers_common.<area>` and
exported from `civers_common/__init__.py`.

---

## Using `civers_common` in a service

### 1. Declare the dependency

In the service's `pyproject.toml`, depend on the package and resolve it from the `uv`
workspace:

```toml
[project]
dependencies = [
    "civers-common",
    # ... other deps
]

[tool.uv.sources]
civers-common = { workspace = true }
```

Then from the repo root:

```bash
uv sync
```

### 2. Use the shared code

The common config classes are designed to be **subclassed**: take the base, add only the
fields your service needs. All shared validation and behavior is inherited, never copied.

```python
from pydantic import Field
from civers_common import BaseKafkaConfig, BaseDomainConfig

class KafkaConfig(BaseKafkaConfig):
    # base provides bootstrap_servers/topics validation, consumer_group sync, etc.
    consumer_group: str = Field(default="archive_generator_group")

class DomainConfig(BaseDomainConfig):
    # base provides name validation, is_wildcard / is_default, webpage_types
    generators: list[str] = Field(default_factory=list)
```

Mixins add shared behavior to your root config model:

```python
from pydantic import BaseModel, Field
from civers_common import DomainResolutionMixin

class ConfigDataModel(DomainResolutionMixin, BaseModel):
    domains: list[DomainConfig] = Field(default_factory=list)

# resolve_domain() / resolve_domain_for_url() are inherited
config.resolve_domain_for_url("https://example.com/page")
```

The shared YAML loader handles defaults → environment overrides → `${VAR:-default}`
expansion:

```python
from civers_common import BaseYamlConfigLoader

raw = BaseYamlConfigLoader(environment="development").load_raw()
config = ConfigDataModel(**raw)
```

---

## Contributing shared code

Add code to `civers_common` only when it is used in production by **two or more services**.
Anything used by a single service, or only by tests, belongs in that service (or in test
helpers) — not here.

To add a new shared area:

1. Create a module under `src/civers_common/<area>/`.
2. Export its public symbols from `src/civers_common/__init__.py`.
3. Add tests under `tests/` (the suite covers the shared contract; services test only their
   own extensions).
4. Keep dependencies minimal — `civers_common` should depend on as little as possible and must
   never depend on a service (the dependency arrow always points *into* `civers_common`).

---

## Project layout

This package uses a **`src` layout**:

```
civers_common/
├── pyproject.toml
├── README.md
├── src/
│   └── civers_common/          # the importable package
│       ├── __init__.py         # public API exports
│       ├── py.typed            # PEP 561 typing marker
│       └── configs/
│           ├── __init__.py
│           ├── models.py       # base config models + mixins
│           ├── loaders.py      # BaseYamlConfigLoader
│           └── exceptions.py   # ConfigurationError
└── tests/                      # OUTSIDE the package (not shipped)
```

### Why the `src` layout (packaging notes)

A **wheel** (`.whl`, Python's built distribution) is a zip that is unpacked directly into
`site-packages`. Whatever directory structure is *inside* the wheel is exactly what becomes
importable after install — so the build must produce a wheel whose top-level directory is the
real package name, `civers_common/`.

The build target in `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/civers_common"]
```

maps `src/civers_common/` to `civers_common/` inside the wheel:

```
civers_common/__init__.py
civers_common/py.typed
civers_common/configs/...
```

`py.typed` is an empty [PEP 561](https://peps.python.org/pep-0561/) marker. Without it, type
checkers ignore a dependency's annotations; with it bundled as `civers_common/py.typed`,
consumers that subclass the base models get full type checking and IDE inference.

---

## Development

```bash
# from repo root
uv sync

# run the test suite
cd civers_common && uv run pytest

# build the wheel (to inspect or produce a distributable)
uv build --wheel civers_common
```
