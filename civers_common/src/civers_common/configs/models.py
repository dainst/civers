"""Base configuration models shared by every CiVers microservice.

Services either use these directly or subclass them to add service-specific fields.
"""

import ipaddress
import re
from typing import Any, Literal,Dict
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .exceptions import ConfigurationError


# ═══════════════════════════════════════════════════════════════════════════
#  BaseDomainConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseDomainConfig(BaseModel):
    """Base domain configuration shared across all CiVers services.

    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        description=(
            "Hostname such as www.example.com (without https:// or a path), "
            "wildcard such as *.example.com, IP address, local name, or default."
        )
    )
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
        if any(char in name for char in "/\\?#@") or any(char.isspace() for char in name):
            raise ValueError(
                "Domain name must be a hostname such as 'www.example.com', "
                "without 'https://', a path, query, fragment, credentials, or spaces"
            )
        if name == "default":
            return name
        if "*" in name:
            # Resolution is suffix matching, so these are the only shapes that can ever
            # match. Anything else validates and then matches nothing — dead config.
            if name != "*" and not name.startswith("*."):
                raise ValueError(
                    f"Wildcard domains must be '*' or start with '*.' (got: {name!r}); "
                    "only suffix matching is supported"
                )
            return name
        if "." in name:
            return name
        if re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            return name
        try:
            # An IPv6 literal has no dot, so it reaches here. normalize_hostname keeps
            # it intact, so an entry naming one has to be allowed to exist.
            ipaddress.ip_address(name)
        except ValueError:
            raise ValueError(
                "Domain name must be a valid domain, wildcard, IP literal, "
                "local hostname, or 'default'"
            ) from None
        return name

    @property
    def is_wildcard(self) -> bool:
        """Return True if this domain is a wildcard pattern."""
        return "*" in self.name

    @property
    def is_default(self) -> bool:
        """Return True if this domain is the default fallback."""
        return self.name.lower() == "default"


# ═══════════════════════════════════════════════════════════════════════════
#  BaseKafkaConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseKafkaConfig(BaseModel):
    """Base Kafka configuration shared across all CiVers services.
    """

    model_config = ConfigDict(extra="ignore")

    bootstrap_servers: str
    topics: dict[str, str]
    consumer_group: str = Field(default="civers_default_group")
    consumer_enable_auto_commit: bool = False
    consumer_request_timeout_ms: int = 30000
    consumer_auto_offset_reset: Literal["earliest", "latest"] = "earliest"
    consumer_max_poll_interval_ms: int = Field(default=600000, gt=0)
    consumer: dict[str, Any] | None = None
    producer_request_timeout_ms: int = 30000
    # acks=0 (no acknowledgement), 1 (leader), -1 / "all" (every in-sync replica).
    producer_acks: Literal[0, 1, -1, "all"] = 1
    producer_retry_backoff_ms: int = 1000
    producer: dict[str, Any] | None = None

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        """Ensure bootstrap_servers is non-empty."""
        if not v or not v.strip():
            raise ValueError("bootstrap_servers cannot be empty")
        return v.strip()

    @field_validator("producer_acks", mode="before")
    @classmethod
    def parse_producer_acks(cls, value: Any) -> Any:
        """Environment expansion yields strings; normalize numeric explicit acks."""
        return int(value) if isinstance(value, str) and value in {"-1", "0", "1"} else value

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
    """Base transport configuration shared across all CiVers services.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: list[str]
    transports: dict[str, dict[str, Any]] = {}

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
        errors = [
            f"Transport '{t}' is enabled but not configured under 'transports'"
            for t in self.enabled
            if not self._has_config(t)
        ]
        if errors:
            raise ValueError(
                f"Transport configuration errors: {'; '.join(errors)}"
            )
        return self

    def _has_config(self, name: str) -> bool:
        """Whether ``name`` resolves to a usable config — the same question the caller asks.
        """
        return self.get_transport_config(name) is not None

    def is_transport_enabled(self, transport: str) -> bool:
        """Return True if the given transport name is in the enabled list."""
        return transport in self.enabled

    def get_transport_config(self, transport: str) -> dict[str, Any] | None:
        """Return the raw config dict for a transport, or None if unknown.
        """
        if transport in self.transports:
            return self.transports[transport]
        if transport in type(self).model_fields:
            typed = getattr(self, transport)
            if isinstance(typed, BaseModel):
                return typed.model_dump()
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  BaseStorageConfig
# ═══════════════════════════════════════════════════════════════════════════


class BaseStorageConfig(BaseModel):
    """Base multi-backend storage configuration.
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
    """

    model_config = ConfigDict(extra="ignore")

    name: str = "civers_service"
    version: str = "1.0.0"
    environment: str = "development"


# ═══════════════════════════════════════════════════════════════════════════
#  Domain Resolution Mixin
# ═══════════════════════════════════════════════════════════════════════════


class DomainResolutionMixin:
    """Mixin providing standardized domain resolution logic.
    """

    @staticmethod
    def normalize_hostname(hostname: str) -> str:
        """Normalize a hostname: lowercase, strip, remove port. IPv6-safe.

        An IPv6 literal is mostly colons, and ``urlparse`` has already removed its
        brackets by the time it arrives here, so a port is stripped only where there is
        unambiguously one to strip.
        """
        if not hostname:
            return hostname
        normalized = hostname.strip().lower()
        if normalized.startswith("["):          # "[::1]:8080" -> "::1"
            end = normalized.find("]")
            if end != -1:
                return normalized[1:end]
        if normalized.count(":") == 1:          # "example.com:8080" -> "example.com"
            return normalized.split(":")[0]
        return normalized                       # bare IPv6 passes through intact

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

        # 2. Wildcard match, most specific first. Sorting by suffix length rather than
        # trusting YAML order means reordering two blocks in a config file cannot
        # silently change which policy a site gets; bare '*' has the empty suffix, so it
        # matches everything and sorts last.
        wildcards = sorted(
            (d for d in self.domains if "*" in d.name),  # type: ignore[attr-defined]
            key=lambda d: len(d.name.replace("*", "")),
            reverse=True,
        )
        for domain_config in wildcards:
            suffix = domain_config.name.replace("*", "")
            if normalized.endswith(suffix):
                if not domain_config.enabled:
                    raise ConfigurationError(
                        f"Domain '{domain_config.name}' is disabled"
                    )
                return domain_config

        # 3. Default fallback
        for domain_config in self.domains:  # type: ignore[attr-defined]
            if domain_config.is_default:
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
