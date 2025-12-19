"""
Configuration models for type-safe configuration management.

This module provides Pydantic models for all application configuration,
ensuring type safety and validation.
"""

from typing import Literal, Optional, Set, Dict, List

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class FilesystemConfig(BaseModel):
    """Filesystem storage provider configuration."""

    path: str = Field(default="archives", description="Path to archives directory")
    timeout_seconds: int = Field(default=10, ge=0, description="Filesystem operation timeout")

    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout(cls, v):
        if v < 0:
            raise ValueError("timeout_seconds must be non-negative")
        return v


class SQLiteConfig(BaseModel):
    """SQLite storage provider configuration."""

    db_path: str = Field(
        default="data/archives.db",
        description="Path to SQLite database file"
    )
    auto_rebuild: bool = Field(
        default=True,
        description="Auto-rebuild index if database empty on startup"
    )
    connection_timeout: int = Field(
        default=10,
        ge=1,
        description="Database connection timeout in seconds"
    )


# class S3Config(BaseModel): # possible extension for future
#     """S3 storage provider configuration (future implementation)."""
    
#     bucket: str
#     region: str
#     access_key_id: str
#     secret_access_key: str
#     prefix: str = "archives/"
#     timeout_seconds: int = Field(default=30, ge=0)


# class DatabaseConfig(BaseModel): # possible extension for future
#     """Database storage provider configuration (future implementation)."""
    
#     connection_string: str
#     timeout_seconds: int = Field(default=15, ge=0)


class CacheConfig(BaseModel):
    """Cache configuration."""
    #add not equal to 0 for ttl_seconds
    ttl_seconds: int = Field(default=60, ge=1, description="Cache TTL in seconds (-1 for no expiration)")
    max_entries: int = Field(default=1000, ge=1, description="Maximum cache entries")

    @field_validator('ttl_seconds')
    @classmethod
    def validate_ttl(cls, v):
        if v < -1 or v == 0:
            raise ValueError("ttl_seconds must be -1 (no expiration) or positive")
        return v


class StorageConfig(BaseModel):
    """Storage configuration."""

    # type: Literal["filesystem", "s3", "database"] = Field(default="filesystem")# possible extension for future
    type: Literal["filesystem", "sqlite"] = Field(default="filesystem")
    filesystem: Optional[FilesystemConfig] = None
    sqlite: Optional[SQLiteConfig] = None
    # s3: Optional[S3Config] = None # possible extension for future
    # database: Optional[DatabaseConfig] = None # possible extension for future
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @model_validator(mode='before')
    @classmethod
    def validate_storage_config(cls, data):
        if isinstance(data, dict):
            storage_type = data.get('type', 'filesystem')

            # Set default filesystem config if type is filesystem and no config provided
            if storage_type == 'filesystem' and 'filesystem' not in data:
                data['filesystem'] = {}

            # SQLite provider needs both SQLite and filesystem configs
            elif storage_type == 'sqlite':
                if 'sqlite' not in data:
                    data['sqlite'] = {}
                # SQLite needs filesystem config for file storage
                if 'filesystem' not in data:
                    data['filesystem'] = {}

            # Validate required configs for other storage types # possible extension for future
            # elif storage_type == 's3' and 's3' not in data:
            #     raise ValueError("S3 configuration required when type is 's3'")
            # elif storage_type == 'database' and 'database' not in data:
            #     raise ValueError("Database configuration required when type is 'database'")

        return data


class ValidationConfig(BaseModel):
    """Input validation configuration."""
    
    # Snapshot ID validation
    snapshot_id_pattern: str = Field(
        default=r'^req_[a-zA-Z0-9\-_]+_\d{8}_\d{6}$',
        description="Regex pattern for snapshot ID validation"
    )
    snapshot_id_max_length: int = Field(
        default=100, 
        ge=10, 
        description="Maximum length for snapshot IDs"
    )
    
    # Directory naming
    snapshot_directory_prefix: str = Field(
        default="req_",
        description="Prefix for snapshot directories"  
    )
    
    # Timestamp formats
    timestamp_formats: List[str] = Field(
        default=[
            '%Y%m%d_%H%M%S', 
            '%Y-%m-%d_%H-%M-%S'
        ],
        description="Supported timestamp formats for parsing"
    )
    
    # File handling
    filename_max_length: int = Field(
        default=255,
        ge=50,
        description="Maximum filename length"
    )
    
    # Artifact types and content mappings
    allowed_artifact_types: Set[str] = Field(
        default={
            "archive.wacz", "metadata.json", "screenshot.png", 
            "singlefile.html", "warc.file", "document.html",
            "dom-snapshot.html", "archive_generator_metadata.json"
        },
        description="Allowed artifact file types"
    )
    
    content_type_mappings: Dict[str, str] = Field(
        default={
            "archive.wacz": "application/zip",
            "metadata.json": "application/json",
            "screenshot.png": "image/png",
            "singlefile.html": "text/html", 
            "warc.file": "application/warc",
            "document.html": "text/html",
            "dom-snapshot.html": "text/html",
            "archive_generator_metadata.json": "application/json"
        },
        description="Content-Type mappings for artifact types"
    )

    @field_validator('snapshot_id_max_length', 'filename_max_length')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Length limits must be positive")
        return v
    
    @field_validator('timestamp_formats')
    @classmethod
    def validate_timestamp_formats(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one timestamp format must be provided")
        return v


class AppConfig(BaseModel):
    """Top-level application configuration."""
    
    model_config = ConfigDict(validate_assignment=True)
    
    storage: StorageConfig = Field(default_factory=StorageConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)