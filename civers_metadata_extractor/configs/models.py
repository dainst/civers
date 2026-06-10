"""Pydantic configuration models for CiVers Metadata Extractor.

Extends the shared ``civers_common`` base config models. Only the per-domain
metadata-extraction fields (``input_source``, ``extractor``, ``mappings``) and the
``StorageConfig`` usage are Metadata Extractor-specific; everything else — including
domain resolution (``resolve_domain`` / ``resolve_domain_for_url``) — follows the
shared defaults.
"""

from typing import Literal

from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseKafkaConfig,
    BaseStorageConfig,
    BaseTransportConfig,
    DomainResolutionMixin,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainConfig(BaseDomainConfig):
    """Metadata Extractor domain config = shared base + extraction fields.

    Since there is a single universal mapper (``FlattenedToIntermediateModelMapper``),
    mapping rules are declared directly on the domain configuration.
    """

    input_source: Literal["html_document", "json_file", "xml_file", "api_response"] = (
        "html_document"
    )
    extractor: str | None = None  # e.g. "jsonld". Required when mappings are present.
    mappings: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def extractor_required_with_mappings(self) -> "DomainConfig":
        if self.mappings and not self.extractor:
            raise ValueError(
                f"Domain '{self.name}' has mappings but no extractor specified. "
                "Add `extractor: <type>` to the domain config (e.g. extractor: jsonld)."
            )
        return self


class KafkaConfig(BaseKafkaConfig):
    """Metadata Extractor Kafka config = shared base with service consumer_group default."""

    consumer_group: str = Field(default="civers_metadata_extractor")


class TransportConfig(BaseTransportConfig):
    """Metadata Extractor transport config = shared base with the ME KafkaConfig type."""

    kafka: KafkaConfig | None = None


class StorageConfig(BaseStorageConfig):
    """Metadata Extractor storage config = shared multi-backend base (used directly)."""


class AppConfig(BaseAppConfig):
    """Metadata Extractor app config = shared base with ME defaults, transport, and storage."""

    name: str = "metadata_extractor"
    transport: TransportConfig | None = None
    storage: StorageConfig | None = None

    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration, falling back to defaults when not set."""
        if self.storage is not None:
            return self.storage
        return StorageConfig()


class ConfigDataModel(DomainResolutionMixin, BaseModel):
    """Root configuration model for CiVers Metadata Extractor.

    Domain resolution (``resolve_domain`` / ``resolve_domain_for_url``) is inherited
    from ``DomainResolutionMixin``. Transport sync is kept locally for now; it will be
    revisited in the Kafka/Transport unification plan.
    """

    model_config = ConfigDict(extra="ignore")

    app: AppConfig
    domains: list[DomainConfig] = Field(default_factory=list)
    transport: TransportConfig | None = None

    @model_validator(mode="after")
    def sync_transport_config(self) -> "ConfigDataModel":
        """Merge root-level transport into app-level transport if needed.

        Handles merging of Kafka topics when both the root and app sections exist.
        """
        if self.transport and self.app.transport:
            if not self.app.transport.kafka and self.transport.kafka:
                self.app.transport.kafka = self.transport.kafka
            elif self.app.transport.kafka and self.transport.kafka:
                combined_topics = self.transport.kafka.topics.copy()
                combined_topics.update(self.app.transport.kafka.topics)
                self.app.transport.kafka.topics = combined_topics
                if (
                    not self.app.transport.kafka.bootstrap_servers
                    and self.transport.kafka.bootstrap_servers
                ):
                    self.app.transport.kafka.bootstrap_servers = (
                        self.transport.kafka.bootstrap_servers
                    )
        elif self.transport and not self.app.transport:
            self.app.transport = self.transport
        elif self.app.transport and not self.transport:
            self.transport = self.app.transport

        return self
