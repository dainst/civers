"""Archive settings built on the shared configuration models."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseStorageConfig,
    BaseTransportConfig,
    DomainResolutionMixin,
)

from archive_generators import ArchiveGeneratorFactory


class GeneratorConfig(BaseModel):
    """Configuration for a specific generator within a domain."""

    name: str
    artifacts: list[str]

    @model_validator(mode="after")
    def validate_capabilities(self) -> "GeneratorConfig":
        generator_class = ArchiveGeneratorFactory.get_generator_class(self.name)
        supported = generator_class.CAPABILITIES
        if not self.artifacts or set(self.artifacts) - set(supported):
            raise ValueError(
                f"Choose at least one supported artifact for {self.name}: {', '.join(supported)}"
            )
        return self


class DomainConfig(BaseDomainConfig):
    """Domain settings and its required list of capture generators."""

    generators: list[GeneratorConfig]

    @field_validator("generators")
    @classmethod
    def check_generators(cls, v: list[GeneratorConfig]) -> list[GeneratorConfig]:
        """Require at least one capture generator."""
        if not v:
            raise ValueError("Domain must have at least one generator defined")
        return v


class TransportConfig(BaseTransportConfig):
    """Shared transport settings with configuration for each adapter."""


class StorageConfig(BaseStorageConfig):
    """Optional publication settings. An empty enabled list keeps captures local.

    StorageManager skips unknown or unconfigured backends.
    """

    enabled: list[str] | None = None
    backends: dict[str, dict[str, Any]] = {}

    @field_validator("enabled")
    @classmethod
    def validate_enabled_backends(cls, v: list[str] | None) -> list[str] | None:
        """Allow an empty enabled list to disable publication."""
        return v

    @model_validator(mode="after")
    def validate_enabled_backends_exist(self) -> "StorageConfig":
        """Allow unconfigured backends; StorageManager skips them at startup."""
        return self

    def get_enabled_backends(self) -> list[str]:
        """Return enabled publication backends, or an empty list."""
        return self.enabled or []


class AppConfig(BaseAppConfig):
    """Capture paths, tool settings and optional publication backends."""

    name: str = "archive_generator"
    version: str = "1.0.0"

    archive_directory: str

    scoop_cli_command: str = "scoop"
    scoop_extra_args: list[str] | None = None
    scoop_timeout_sec: int = Field(default=120, gt=0)

    singlefile_binary_path: str = "/single-file-x86_64-linux"
    singlefile_timeout_sec: int = Field(default=60, gt=0)

    # Shared folder for Browsertrix job arguments and results.
    browsertrix_jobs_dir: str = "/jobs"
    browsertrix_timeout_sec: int = Field(default=300, gt=0)
    browsertrix_extra_args: list[str] | None = None

    ssrf_protection_enabled: bool = True

    storage: StorageConfig

    @field_validator(
        "archive_directory",
        "scoop_cli_command",
        "singlefile_binary_path",
        "browsertrix_jobs_dir",
    )
    @classmethod
    def strip_and_reject_blank(cls, v: str, info: ValidationInfo) -> str:
        """Trim paths and commands; raise ValueError if the result is empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"'{info.field_name}' cannot be blank")
        return stripped

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


class ConfigDataModel(DomainResolutionMixin, BaseModel):
    """Root archive configuration. Transports are configured at the root.

    DomainResolutionMixin selects the domain settings for a URL.
    """

    domains: list[DomainConfig]
    app: AppConfig
    transport: TransportConfig
