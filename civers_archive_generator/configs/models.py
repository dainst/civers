from typing import List, Literal, Dict, Optional, Any
from pydantic import BaseModel, field_validator, model_validator, Field
from pathlib import Path
import os

class GeneratorConfig(BaseModel):
    """Configuration for a specific generator within a domain"""
    name: str
    artifacts: List[str]

class DomainConfig(BaseModel):
    """Configuration for a specific domain's archiving behavior"""
    name: str
    generators: List[GeneratorConfig]
    webpage_types: Literal["dynamic", "static"]
    enabled: bool = True
    description: str = ""

    @property
    def is_wildcard(self) -> bool:
        """Check if this is a wildcard domain pattern."""
        return "*" in self.name

    @field_validator("generators")
    def check_generators(cls, v):
        if not v:
            raise ValueError("Domain must have at least one generator defined")
        return v

class KafkaConfig(BaseModel):
    """Kafka transport configuration"""
    bootstrap_servers: str
    topics: Dict[str, str]
    consumer_group: str
    # Kafka-specific monitoring and health check settings
    # TODO: These can be extended in the future
    health_check_enabled: bool = True
    monitoring_enabled: bool = True

class TransportConfig(BaseModel):
    """
    Extensible transport configuration using a plugin-style approach.
    
    New transports can be added by:
    1. Adding their config to the YAML under 'transports.{transport_name}'
    2. The transport implementation reads its config from the generic 'transports' dict
    
    Example YAML:
    app:
      transports:
        kafka:
          bootstrap_servers: "localhost:29092"
          topics: {...}
        http:
          host: "localhost"
          port: 8000
        custom_transport:
          any_custom_config: "value"
    """
    # Currently enabled transports (at least one required)
    enabled: List[str]
    
    # Transport-specific configurations (extensible)
    kafka: Optional[KafkaConfig] = None
    
    # Generic transport configurations for extensibility
    # New transports can add their config here without changing the model
    transports: Dict[str, Dict[str, Any]] = {}
    
    @field_validator("enabled")
    def validate_enabled_transports(cls, v):
        """Validate that at least one transport is enabled"""
        if not v:
            raise ValueError("At least one transport must be enabled")
        return v
    
    def is_transport_enabled(self, transport: str) -> bool:
        """Check if a specific transport is enabled"""
        return transport in self.enabled
    
    def get_transport_config(self, transport: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific transport"""
        if transport == "kafka" and self.kafka:
            return self.kafka.model_dump()
        return self.transports.get(transport)

class StorageConfig(BaseModel):
    """
    Extensible storage configuration with multi-backend support.
    
    Storage backends can be added by:
    1. Adding their config to the YAML under 'storage.backends.{backend_name}'
    2. The storage implementation reads its config from the 'backends' dict
    
    Example YAML:
    app:
      storage:
        enabled:
          - local_file
          - civers_rest_api
        backends:
          local_file:
            base_path: "archives/metadata"
          civers_rest_api:
            upload_url: "http://localhost:8000/api/upload"
    """
    # List of enabled storage backends (required)
    enabled: List[str]
    
    # Backend-specific configurations
    backends: Dict[str, Dict[str, Any]] = {
        "local_file": {"base_path": "archives"}
    }
    
    @field_validator('enabled')
    @classmethod
    def validate_enabled_backends(cls, v):
        """Validate that enabled list is not empty."""
        if len(v) == 0:
            raise ValueError("'enabled' list cannot be empty")
        return v
    
    def model_post_init(self, __context):
        """Validate that all enabled backends have configurations."""
        for backend_name in self.enabled:
            if backend_name not in self.backends:
                raise ValueError(
                    f"Backend '{backend_name}' is enabled but not configured in 'backends'"
                )
    
    def get_enabled_backends(self) -> List[str]:
        """Get list of enabled storage backends."""
        return self.enabled
    
    def get_backend_config(self, backend: str) -> Dict[str, Any]:
        """Get configuration for the specified storage backend."""
        return self.backends.get(backend, {})

class AppConfig(BaseModel):
    """Core application configuration"""
    name: str = Field(default="Civers Archive Generator", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    
    # Core application settings
    archive_directory: str

    # Scoop integration settings
    # Command to invoke Scoop (can be an absolute path or a command on PATH). Examples: "scoop", "npx scoop"
    scoop_cli_command: str = "scoop"
    # Additional CLI arguments to pass to Scoop
    scoop_extra_args: Optional[List[str]] = None
    # Timeout for Scoop process in seconds
    scoop_timeout_sec: int = 120
    
    # SingleFile integration settings
    singlefile_binary_path: str = "archive_generators/single-file-x86_64-linux"
    singlefile_timeout_sec: int = 60
    
    # Transport configuration — optional here; populated from root-level transport in ConfigDataModel
    transport: Optional[TransportConfig] = None
    
    # Security configuration
    ssrf_protection_enabled: bool = True

    # Storage configuration (required)
    storage: StorageConfig
    
    def is_transport_enabled(self, transport: str) -> bool:
        """Check if a specific transport is enabled"""
        return self.transport.is_transport_enabled(transport)
    
    def get_kafka_config(self) -> Optional[KafkaConfig]:
        """Get Kafka configuration from transport settings"""
        return self.transport.kafka
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration"""
        return self.storage
    
    def validate_singlefile_config(self):
        """Validate SingleFile binary exists and is executable"""
        binary_path = Path(self.singlefile_binary_path)
        if not binary_path.exists():
            raise ValueError(f"SingleFile binary not found: {self.singlefile_binary_path}")
        if not os.access(binary_path, os.X_OK):
            raise ValueError(f"SingleFile binary not executable: {self.singlefile_binary_path}")
        return True

class ConfigDataModel(BaseModel):
    domains: List[DomainConfig]
    app: AppConfig
    transport: Optional[TransportConfig] = None

    @model_validator(mode="after")
    def sync_transport_config(self) -> "ConfigDataModel":
        """Sync root-level transport into app.transport if not already set."""
        if self.transport and not self.app.transport:
            self.app.transport = self.transport
        return self
