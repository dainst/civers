"""Pydantic configuration models for CiVers Archive Generator.

Extends the shared civers_common base config models. AG-specific additions:
- ``GeneratorConfig`` / ``DomainConfig.generators`` — per-domain archiver list
- ``StorageConfig`` — multi-backend storage (enabled is required in AG)
- ``AppConfig`` — archive directory, scoop/singlefile settings, storage
"""

import os
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator

from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseKafkaConfig,
    BaseStorageConfig,
    BaseTransportConfig,
)


class GeneratorConfig(BaseModel):
    """Configuration for a specific generator within a domain."""

    name: str
    artifacts: list[str]


class DomainConfig(BaseDomainConfig):
    """Archive Generator domain config = shared base + per-domain generators list."""

    generators: list[GeneratorConfig]

    @field_validator("generators")
    @classmethod
    def check_generators(cls, v: list[GeneratorConfig]) -> list[GeneratorConfig]:
        if not v:
            raise ValueError("Domain must have at least one generator defined")
        return v


class KafkaConfig(BaseKafkaConfig):
    """Archive Generator Kafka config — uses shared base defaults unchanged."""


class TransportConfig(BaseTransportConfig):
    """Archive Generator transport config = shared base with the AG KafkaConfig type."""

    kafka: KafkaConfig | None = None


class StorageConfig(BaseStorageConfig):
    """Archive Generator storage config.

    ``enabled`` is required in AG (no single-backend legacy mode).
    All validators and helper methods are inherited from ``BaseStorageConfig``.

    TODO (domain-resolution follow-up): when AG's service layer is refactored,
    add ``DomainResolutionMixin`` to ``ConfigDataModel`` and update
    ``ArchiveService.get_domain_config()`` to use ``config.resolve_domain()``.
    """

    enabled: list[str]  # required (overrides Optional default in BaseStorageConfig)


class AppConfig(BaseAppConfig):
    """Archive Generator app config = shared base + AG-specific settings."""

    name: str = "archive_generator"
    version: str = "1.0.0"
    transport: TransportConfig | None = None

    archive_directory: str

    scoop_cli_command: str = "scoop"
    scoop_extra_args: list[str] | None = None
    scoop_timeout_sec: int = 120

    singlefile_binary_path: str = "archive_generators/single-file-x86_64-linux"
    singlefile_timeout_sec: int = 60

    ssrf_protection_enabled: bool = True

    storage: StorageConfig

    def get_storage_config(self) -> StorageConfig:
        """Return the storage configuration."""
        return self.storage

    def validate_singlefile_config(self) -> bool:
        """Validate that the SingleFile binary exists and is executable."""
        binary_path = Path(self.singlefile_binary_path)
        if not binary_path.exists():
            raise ValueError(
                f"SingleFile binary not found: {self.singlefile_binary_path}"
            )
        if not os.access(binary_path, os.X_OK):
            raise ValueError(
                f"SingleFile binary not executable: {self.singlefile_binary_path}"
            )
        return True


class ConfigDataModel(BaseModel):
    """Root configuration model for CiVers Archive Generator.

    Transport sync is kept locally for now; it will be revisited in the
    Kafka/Transport unification plan.

    Domain resolution follow-up: ``DomainResolutionMixin`` will be added here
    and ``ArchiveService.get_domain_config()`` updated when AG's service layer
    is refactored (see ``StorageConfig`` docstring).
    """

    domains: list[DomainConfig]
    app: AppConfig
    transport: TransportConfig | None = None

    @model_validator(mode="after")
    def sync_transport_config(self) -> "ConfigDataModel":
        """Sync root-level transport into app.transport if not already set."""
        if self.transport and not self.app.transport:
            self.app.transport = self.transport
        return self
