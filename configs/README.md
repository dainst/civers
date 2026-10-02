# Configuration

Runtime settings live in [`data/`](data/), with one folder per component:
`archive_generator`, `metadata_extractor`, `orchestrator`, `web_interface`, and
`change_detection`. Each component keeps its Python models and loader beside its
code. Change Detection has configuration models but no running service.

## How settings are loaded

1. Read `defaults/*.yaml` in filename order.
2. Merge `environments/<name>.yaml` over those defaults.
3. Expand environment-variable placeholders.
4. Validate the result against the component's Python model.

Dictionaries merge by key. Lists replace the entire previous list: an environment's
`domains` list replaces all default domains.

An explicit loader argument or `CONFIG_ENVIRONMENT` selects the environment.
Otherwise, the loader detects Docker, then tests, and falls back to `development`.
An explicitly selected environment file must exist. `CONFIG_DIR` can select a
different component configuration directory.