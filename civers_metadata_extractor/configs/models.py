from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DomainConfig(BaseModel):
    """Configuration for a specific domain's metadata extraction behavior.

    Since we now have only one universal mapper (FlattenedToIntermediateModelMapper),
    mappings are defined directly in the domain configuration.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    input_source: Literal["html_document", "json_file", "xml_file", "api_response"] = (
        "html_document"
    )
    extractor: str | None = None  # e.g. "jsonld". Required when mappings present.
    mappings: dict[str, str] = Field(
        default_factory=dict
    )  # Mapping rules: source_field -> target_field

    @model_validator(mode="after")
    def extractor_required_with_mappings(self) -> "DomainConfig":
        if self.mappings and not self.extractor:
            raise ValueError(
                f"Domain '{self.name}' has mappings but no extractor specified. "
                "Add `extractor: <type>` to the domain config (e.g. extractor: jsonld)."
            )
        return self

    @field_validator("name")
    @classmethod
    def validate_domain_name(cls, v):
        """Ensure domain name is valid or a special identifier."""
        if not v:
            raise ValueError("Domain name cannot be empty")

        # Allow special 'default' keyword
        if v == "default":
            return v

        # Allow wildcards (*.domain.com) or standard domains (with dots)
        if "." in v or "*" in v:
            return v

        # Allow local hostnames (localhost, arachne_local_demo, etc.)
        # Check if it consists of alphanumeric characters, underscores or hyphens
        import re

        if re.match(r"^[a-zA-Z0-9_-]+$", v):
            return v

        raise ValueError(
            "Domain name must be a valid domain, wildcard, local hostname, or 'default'"
        )


class KafkaConfig(BaseModel):
    """Kafka transport configuration with support for shared structure."""

    model_config = ConfigDict(extra="ignore")

    bootstrap_servers: str
    topics: dict[str, str]
    consumer_group: str = Field(default="civers_metadata_extractor")
    # Kafka-specific monitoring and health check settings
    health_check_enabled: bool = True
    monitoring_enabled: bool = True

    # Support for shared consumer.group_id structure
    consumer: dict[str, Any] | None = None

    @model_validator(mode="after")
    def sync_consumer_group(self) -> "KafkaConfig":
        """Sync consumer_group with consumer.group_id if present."""
        if self.consumer and "group_id" in self.consumer:
            self.consumer_group = self.consumer["group_id"]
        return self

    @field_validator("topics")
    @classmethod
    def validate_metadata_topics(cls, v):
        """Validate that at least one topic is configured"""
        if not v or len(v) < 1:
            raise ValueError("At least one topic must be configured")

        return v

    def get_topic(self, topic_name: str) -> str | None:
        """Get Kafka topic name for a specific event type"""
        return self.topics.get(topic_name)


class TransportConfig(BaseModel):
    """
    Transport configuration using dedicated classes for each transport type.

    New transports are added by:
    1. Creating a new dedicated Pydantic class (e.g., RabbitMQConfig)
    2. Adding it as a field to this class
    3. Updating the get_transport_config() method

    Example:
    app:
      transport:
        enabled: ["kafka"]
        kafka:
          bootstrap_servers: "localhost:29092"
          topics: {...}
    """

    model_config = ConfigDict(extra="ignore")

    # Currently enabled transports (at least one required)
    enabled: list[str]

    # Dedicated transport configurations
    kafka: KafkaConfig | None = None

    @field_validator("enabled")
    def validate_enabled_transports(cls, v):
        """Validate that at least one transport is enabled"""
        if not v:
            raise ValueError("At least one transport must be enabled")
        return v

    @model_validator(mode="after")
    def validate_enabled_transports_have_config(self):
        """Validate that all enabled transports have corresponding configuration"""
        # Define mapping between enabled transport names and config fields
        transport_config_mapping = {
            "kafka": self.kafka,
            # Add new transports here as they are implemented
            # "rabbitmq": self.rabbitmq,
            # "http": self.http,
        }

        missing_configs = []
        for transport in self.enabled:
            if transport not in transport_config_mapping:
                missing_configs.append(
                    f"Transport '{transport}' is enabled but not supported. "
                    f"Available transports: {list(transport_config_mapping.keys())}"
                )
            elif transport_config_mapping[transport] is None:
                missing_configs.append(
                    f"Transport '{transport}' is enabled but no configuration provided"
                )

        if missing_configs:
            raise ValueError(f"Transport configuration errors: {'; '.join(missing_configs)}")

        return self

    def is_transport_enabled(self, transport: str) -> bool:
        """Check if a specific transport is enabled"""
        return transport in self.enabled

    def get_transport_config(self, transport: str) -> dict[str, Any] | None:
        """Get configuration for a specific transport"""
        transport_config_mapping = {
            "kafka": self.kafka,
            # Add new transports here as they are implemented
            # "rabbitmq": self.rabbitmq,
            # "http": self.http,
        }

        config = transport_config_mapping.get(transport)
        if config:
            return config.model_dump()
        return None


class StorageConfig(BaseModel):
    """
    Multi-backend storage configuration supporting simultaneous storage to multiple backends.

    Supports both single-backend and multi-backend modes:
    - Single backend (legacy): Uses 'backend' field
    - Multi-backend (new): Uses 'enabled' list field

    Example YAML (Multi-backend):
    app:
      storage:
        enabled:
          - local_file
          - civers_rest_api
        backends:
          local_file:
            base_path: "output/metadata"
            create_subdirectories: true
          civers_rest_api:
            upload_url: "http://localhost:8000/api/upload"
            timeout_seconds: 30
            retry_attempts: 3
            verify_ssl: true
            auth:
              enabled: false
          s3:
            bucket: "my-archives"
            region: "us-east-1"

    Example YAML (Single-backend - backward compatible):
    app:
      storage:
        backend: "local_file"
        backends:
          local_file:
            base_path: "archives"
    """

    # Multi-backend mode: List of enabled storage backends
    enabled: list[str] | None = None

    # Legacy single-backend mode: Currently active storage backend
    backend: str = "local_file"

    # Backend-specific configurations (extensible)
    backends: dict[str, dict[str, Any]] = {"local_file": {"base_path": "archives"}}

    @field_validator("enabled")
    @classmethod
    def validate_enabled_backends(cls, v: list[str] | None) -> list[str] | None:
        """Validate that enabled backends list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError(
                "'enabled' list cannot be empty. "
                "Provide at least one backend or use 'backend' field."
            )
        return v

    @model_validator(mode="after")
    def validate_enabled_backends_exist(self) -> "StorageConfig":
        """Validate that all enabled backends have configurations."""
        enabled_list = self.get_enabled_backends()

        for backend_name in enabled_list:
            if backend_name not in self.backends:
                raise ValueError(
                    f"Backend '{backend_name}' is enabled but has no configuration in 'backends'. "
                    f"Available backends: {', '.join(self.backends.keys())}"
                )

        return self

    def get_enabled_backends(self) -> list[str]:
        """
        Get list of enabled backends.

        Returns 'enabled' list if set (multi-backend mode),
        otherwise returns single 'backend' as a list (legacy mode).

        Returns:
            List of enabled backend names
        """
        if self.enabled is not None:
            return self.enabled
        return [self.backend]

    def get_backend_config(self, backend: str | None = None) -> dict[str, Any]:
        """
        Get configuration for the active or specified storage backend.

        Args:
            backend: Backend name, or None to use first enabled backend

        Returns:
            Backend configuration dictionary
        """
        if backend is None:
            # Get first enabled backend
            enabled = self.get_enabled_backends()
            backend_name = enabled[0] if enabled else self.backend
        else:
            backend_name = backend

        return self.backends.get(backend_name, {})


class AppConfig(BaseModel):
    """Core application configuration"""

    model_config = ConfigDict(extra="ignore")

    name: str = "metadata_extractor"
    version: str = "1.0.0"
    environment: str = "development"

    # Transport configuration - can be direct or nested under 'transport'
    transport: TransportConfig | None = None
    # Special case for shared app.yaml which might have transport settings
    # We'll handle this in get_kafka_config

    # Storage configuration (extensible, future planning)
    storage: StorageConfig | None = None

    def is_transport_enabled(self, transport: str) -> bool:
        """Check if a specific transport is enabled"""
        if self.transport:
            return self.transport.is_transport_enabled(transport)
        return False

    def get_kafka_config(self) -> KafkaConfig | None:
        """Get Kafka configuration from transport settings"""
        if self.transport and self.transport.kafka:
            return self.transport.kafka
        return None

    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration, creating default if not present"""
        if self.storage is not None:
            return self.storage

        # Default local file storage for now
        return StorageConfig()


class ConfigDataModel(BaseModel):
    """
    Main configuration model for the Metadata Extractor.

    This model supports the hierarchical configuration structure used by all
    CiVers components, allowing for seamless integration and shared defaults.
    """

    app: AppConfig
    domains: list[DomainConfig]

    # Capture root-level transport from shared kafka.yaml
    transport: TransportConfig | None = None

    @model_validator(mode="after")
    def sync_transport_config(self) -> "ConfigDataModel":
        """
        Merge root-level transport config into app-level transport if needed.
        Handles merging of topics if both sections exist.
        """
        if self.transport and self.app.transport:
            # Merge root-level into app-level
            if not self.app.transport.kafka and self.transport.kafka:
                self.app.transport.kafka = self.transport.kafka
            elif self.app.transport.kafka and self.transport.kafka:
                # Merge topics dictionaries
                combined_topics = self.transport.kafka.topics.copy()
                combined_topics.update(self.app.transport.kafka.topics)
                self.app.transport.kafka.topics = combined_topics

                # Ensure bootstrap servers are set if missing in one
                if (
                    not self.app.transport.kafka.bootstrap_servers
                    and self.transport.kafka.bootstrap_servers
                ):
                    self.app.transport.kafka.bootstrap_servers = (
                        self.transport.kafka.bootstrap_servers
                    )

        # Fallback sync if one is missing
        if self.transport and not self.app.transport:
            self.app.transport = self.transport
        elif self.app.transport and not self.transport:
            self.transport = self.app.transport

        return self

    @classmethod
    def load(cls, config_dir: str | None = None, environment: str | None = None):
        """
        Helper to load configuration from directory.
        """
        from .loaders import YamlFileConfigLoader

        loader = YamlFileConfigLoader(
            config_dir=Path(config_dir) if config_dir else None, environment=environment
        )
        return loader.load()

    # Domain configuration methods

    def normalize_domain(self, domain: str) -> str:
        """
        Normalize domain name for consistent matching.

        Handles common domain variations:
        - Converts to lowercase
        - Removes port numbers
        - Strips whitespace

        Args:
            domain: Raw domain name

        Returns:
            Normalized domain name
        """
        if not domain:
            return domain

        # Convert to lowercase and strip whitespace
        normalized = domain.lower().strip()

        # Remove port numbers (e.g., example.com:443 -> example.com)
        if ":" in normalized:
            normalized = normalized.split(":")[0]

        # Remove www prefix for broader matching (optional - can be enabled if needed)
        # if normalized.startswith('www.'):
        #     normalized = normalized[4:]

        return normalized

    def get_domain_config(self, domain_name: str) -> DomainConfig:
        """
        Get the configuration for a specific domain with normalized matching.

        Args:
            domain_name: The domain name to get configuration for

        Returns:
            DomainConfig object for the domain

        Raises:
            ValueError: If domain is not supported
        """
        normalized_input = self.normalize_domain(domain_name)

        for domain_config in self.domains:
            if self.normalize_domain(domain_config.name) == normalized_input:
                return domain_config

        # If no match found, provide helpful error with available domains
        available_domains = [domain.name for domain in self.domains]
        raise ValueError(
            f"Domain '{domain_name}' (normalized: '{normalized_input}') is not supported. "
            f"Available domains: {available_domains}"
        )

    def get_domain_config_as_dict(self, domain_name: str) -> dict[str, Any]:
        """
        Get domain configuration as dictionary for processing.

        Args:
            domain_name: The domain name to get configuration for

        Returns:
            Domain configuration as dict

        Raises:
            ValueError: If domain is not supported
        """
        domain_config = self.get_domain_config(domain_name)
        return domain_config.model_dump()

    def get_supported_domains(self) -> list[str]:
        """
        Get list of domain names supported by the system.

        Returns:
            List of domain names (e.g., ['example.com', 'arachne.dainst.org'])
        """
        return [domain.name for domain in self.domains]

    def is_domain_supported(self, domain_name: str) -> bool:
        """
        Check if a domain is supported (has configuration) using normalized matching.

        Args:
            domain_name: Domain name to check

        Returns:
            True if domain is supported, False otherwise
        """
        try:
            self.get_domain_config(domain_name)
            return True
        except ValueError:
            return False

    def get_domain_mapper_type(self, domain_name: str) -> str:
        """
        Get mapper type for a specific domain.

        Since we now have only one universal mapper, this always returns
        'flattened_to_intermediate' regardless of domain.

        Args:
            domain_name: Domain name

        Returns:
            Mapper type string (always 'flattened_to_intermediate')

        Raises:
            ValueError: If domain is not supported
        """
        # Validate that domain exists
        self.get_domain_config(domain_name)
        return "flattened_to_intermediate"

    def get_domain_mappings(self, domain_name: str) -> dict[str, str]:
        """
        Get mappings for a specific domain.

        Args:
            domain_name: Domain name

        Returns:
            Dictionary of mappings

        Raises:
            ValueError: If domain is not supported
        """
        domain_config = self.get_domain_config(domain_name)
        return domain_config.mappings

    def get_domain_input_source(self, domain_name: str) -> str:
        """
        Get input source type for a specific domain.

        Args:
            domain_name: Domain name

        Returns:
            Input source type string

        Raises:
            ValueError: If domain is not supported
        """
        domain_config = self.get_domain_config(domain_name)
        return domain_config.input_source

    def validate_domain_configurations(self) -> dict[str, Any]:
        """
        Validate all domain configurations.

        Returns:
            Validation results
        """
        results: dict[str, Any] = {
            "valid": True,
            "total_domains": len(self.domains),
            "valid_domains": [],
            "invalid_domains": [],
            "errors": [],
        }

        if not self.domains:
            results["valid"] = False
            results["errors"].append("No domains configured")
            return results

        for domain in self.domains:
            try:
                # Validate domain name format
                if not domain.name or (
                    "." not in domain.name and "*" not in domain.name and domain.name != "default"
                ):
                    results["invalid_domains"].append(domain.name)
                    results["errors"].append(f"Invalid domain name: {domain.name}")
                    continue

                # Mappings are now optional in the unified configuration
                # but we'll log a warning if they are completely missing for non-default domains
                if not domain.mappings and domain.name not in ["default", "*.dainst.org"]:
                    # Just an info/debug, not a validation failure
                    pass

                results["valid_domains"].append(domain.name)

            except Exception as e:
                results["invalid_domains"].append(domain.name)
                results["errors"].append(f"Error validating domain {domain.name}: {str(e)}")

        results["valid"] = len(results["invalid_domains"]) == 0
        return results
