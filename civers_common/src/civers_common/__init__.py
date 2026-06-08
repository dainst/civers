"""civers_common — Shared configuration infrastructure for CiVers microservices."""

from .configs.exceptions import ConfigurationError
from .configs.loaders import BaseYamlConfigLoader
from .configs.models import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseKafkaConfig,
    BaseStorageConfig,
    BaseTransportConfig,
    DomainResolutionMixin,
)

__all__ = [
    # Base models
    "BaseAppConfig",
    "BaseDomainConfig",
    "BaseKafkaConfig",
    "BaseStorageConfig",
    "BaseTransportConfig",
    # Mixins
    "DomainResolutionMixin",
    # Loader
    "BaseYamlConfigLoader",
    # Exceptions
    "ConfigurationError",
]
