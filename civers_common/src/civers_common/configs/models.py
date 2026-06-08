"""Golden Template base classes for CiVers microservice configuration.

Services IMPORT these classes and either:
  (a) Use them directly (if no extensions needed), or
  (b) Subclass them to add service-specific fields.

Base classes derived from the 4 mature services (AG, ME, ORCH, AWI).
"""

import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .exceptions import ConfigurationError


# ═══════════════════════════════════════════════════════════════════════════
#  BaseDomainConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseDomainConfig(BaseModel):
    """Base domain configuration shared across all CiVers services.

    Services extend this with their own fields:
    - CD adds: change_detection
    - AG adds: generators
    - ME adds: input_source, extractor, mappings
    - ORCH adds: workflow
    - AWI adds: display_name
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    enabled: bool = True
    description: str = ""
    webpage_types: Literal["dynamic", "static"] = "dynamic"

    @field_validator("name")
    @classmethod
    def validate_domain_name(cls, v: str) -> str:
        """Validate domain name: FQDN, wildcard, local hostname, or 'default'."""
        if not v or not v.strip():
            raise ValueError("Domain name cannot be empty")
        name = v.strip()
        if name == "default":
            return name
        if "." in name or "*" in name:
            return name
        if re.match(r"^[a-zA-Z0-9_-]+$", name):
            return name
        raise ValueError(
            "Domain name must be a valid domain, wildcard, local hostname, or 'default'"
        )

    @property
    def is_wildcard(self) -> bool:
        """Check if this is a wildcard domain pattern."""
        return "*" in self.name

    @property
    def is_default(self) -> bool:
        """Check if this is the default fallback domain."""
        return self.name.lower() == "default"


# ═══════════════════════════════════════════════════════════════════════════
#  BaseKafkaConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseKafkaConfig(BaseModel):
    # TODO: This might change when we refactor the transport service.

    """Base Kafka configuration shared across all CiVers services.

    Services extend this with their own fields:
    - ORCH adds: producer, component_mappings
    - AWI adds: producer, connection_retry_*
    - CD/AG/ME use base directly (with different consumer_group defaults)
    """

    model_config = ConfigDict(extra="ignore")

    bootstrap_servers: str
    topics: dict[str, str]
    consumer_group: str = Field(default="civers_default_group")
    consumer: dict[str, Any] | None = None

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        """Ensure bootstrap_servers is non-empty."""
        if not v or not v.strip():
            raise ValueError("bootstrap_servers cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def sync_consumer_group(self) -> "BaseKafkaConfig":
        """Sync consumer_group from nested consumer.group_id if present."""
        if self.consumer and "group_id" in self.consumer:
            self.consumer_group = self.consumer["group_id"]
        return self

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, v: dict[str, str]) -> dict[str, str]:
        """Ensure at least one Kafka topic is configured."""
        if not v:
            raise ValueError("At least one Kafka topic must be configured")
        return v


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTransportConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseTransportConfig(BaseModel):
    # TODO: This might change when we refactor the transport service.
    """Base transport configuration shared across all CiVers services."""

    model_config = ConfigDict(extra="ignore")

    enabled: list[str]
    kafka: BaseKafkaConfig | None = None

    @field_validator("enabled")
    @classmethod
    def validate_enabled(cls, v: list[str]) -> list[str]:
        """Ensure at least one transport is enabled."""
        if not v:
            raise ValueError("At least one transport must be enabled")
        return v

    @model_validator(mode="after")
    def validate_enabled_have_config(self) -> "BaseTransportConfig":
        """Ensure every enabled transport has a corresponding configuration."""
        transport_config_mapping = {"kafka": self.kafka}
        errors = []
        for t in self.enabled:
            if t not in transport_config_mapping:
                errors.append(f"Transport '{t}' is not supported")
            elif transport_config_mapping[t] is None:
                errors.append(
                    f"Transport '{t}' is enabled but not configured"
                )
        if errors:
            raise ValueError(
                f"Transport configuration errors: {'; '.join(errors)}"
            )
        return self


# ═══════════════════════════════════════════════════════════════════════════
#  BaseStorageConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseStorageConfig(BaseModel):
    # TODO: This might change when we refactor the storage service.

    """Base multi-backend storage configuration.

    Supports both multi-backend mode (enabled list) and
    legacy single-backend mode (backend field).

    Used by: AG, ME.
    NOT used by: CD (no storage), AWI (own StorageConfig with type+providers).
    """

    model_config = ConfigDict(extra="ignore")

    enabled: list[str] | None = None
    backend: str = "local_file"
    backends: dict[str, dict[str, Any]] = {"local_file": {"base_path": "archives"}}

    @field_validator("enabled")
    @classmethod
    def validate_enabled_backends(cls, v: list[str] | None) -> list[str] | None:
        """Validate that enabled list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError(
                "'enabled' list cannot be empty. "
                "Provide at least one backend or use 'backend' field."
            )
        return v

    @model_validator(mode="after")
    def validate_enabled_backends_exist(self) -> "BaseStorageConfig":
        """Validate that all enabled backends have configurations."""
        for backend_name in self.get_enabled_backends():
            if backend_name not in self.backends:
                raise ValueError(
                    f"Backend '{backend_name}' is enabled but not configured in 'backends'. "
                    f"Available backends: {', '.join(self.backends.keys())}"
                )
        return self

    def get_enabled_backends(self) -> list[str]:
        """Get list of enabled backends."""
        if self.enabled is not None:
            return self.enabled
        return [self.backend]

    def get_backend_config(self, backend: str | None = None) -> dict[str, Any]:
        """Get configuration for a specific storage backend."""
        if backend is None:
            enabled = self.get_enabled_backends()
            backend_name = enabled[0] if enabled else self.backend
        else:
            backend_name = backend
        return self.backends.get(backend_name, {})


# ═══════════════════════════════════════════════════════════════════════════
#  BaseAppConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseAppConfig(BaseModel):
    """Base application configuration shared across all CiVers services.

    Services extend this with their own fields:
    - AG adds: archive_directory, scoop_*, singlefile_*, storage
    - ME adds: storage
    - AWI adds: description, service_name, logging
    - ORCH adds: metadata
    """

    model_config = ConfigDict(extra="ignore")

    name: str = "civers_service"
    version: str = "1.0.0"
    environment: str = "development"
    transport: BaseTransportConfig | None = None

    def get_kafka_config(self) -> BaseKafkaConfig | None:
        """Get Kafka configuration from transport settings."""
        return self.transport.kafka if self.transport else None


# ═══════════════════════════════════════════════════════════════════════════
#  Domain Resolution Mixin
# ═══════════════════════════════════════════════════════════════════════════


class DomainResolutionMixin:
    """Mixin providing standardized domain resolution logic.

    Expects the consuming class to have:
    - self.domains: list[BaseDomainConfig]

    Resolution order: exact match → wildcard → default → raise.
    """

    @staticmethod
    def normalize_hostname(hostname: str) -> str:
        """Normalize a hostname: lowercase, strip, remove port."""
        if not hostname:
            return hostname
        normalized = hostname.strip().lower()
        if ":" in normalized:
            normalized = normalized.split(":")[0]
        return normalized

    def resolve_domain(self, identifier: str) -> "BaseDomainConfig":
        """Resolve domain configuration by hostname or domain name.

        Resolution order: exact match → wildcard → default.
        Raises ConfigurationError if no match found or domain is disabled.
        """
        normalized = self.normalize_hostname(identifier)

        # 1. Exact match
        for domain_config in self.domains:  # type: ignore[attr-defined]
            if "*" not in domain_config.name and self.normalize_hostname(
                domain_config.name
            ) == normalized:
                if not domain_config.enabled:
                    raise ConfigurationError(
                        f"Domain '{domain_config.name}' is disabled"
                    )
                return domain_config

        # 2. Wildcard match
        for domain_config in self.domains:  # type: ignore[attr-defined]
            if "*" in domain_config.name:
                suffix = domain_config.name.replace("*", "")
                if suffix and normalized.endswith(suffix):
                    if not domain_config.enabled:
                        raise ConfigurationError(
                            f"Domain '{domain_config.name}' is disabled"
                        )
                    return domain_config

        # 3. Default fallback
        for domain_config in self.domains:  # type: ignore[attr-defined]
            if domain_config.name == "default":
                if not domain_config.enabled:
                    raise ConfigurationError(
                        "Default domain entry is disabled"
                    )
                return domain_config

        available = [d.name for d in self.domains]  # type: ignore[attr-defined]
        raise ConfigurationError(
            f"No domain configuration for '{identifier}' "
            f"(normalized: '{normalized}'). "
            f"Available domains: {available}"
        )

    def resolve_domain_for_url(self, url: str) -> "BaseDomainConfig":
        """Resolve domain configuration from a full URL."""
        parsed = urlparse(url)
        if not parsed.hostname:
            raise ConfigurationError(
                f"Could not extract hostname from URL: {url}"
            )
        return self.resolve_domain(parsed.hostname)


