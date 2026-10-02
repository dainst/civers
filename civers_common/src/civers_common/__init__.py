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
from .messaging import (
    Command,
    CommandBus,
    Result,
    ResultStatus,
    is_valid_request_id,
)
from .transport import (
    Transport,
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
    # Messaging
    "Command",
    "Result",
    "ResultStatus",
    "CommandBus",
    "is_valid_request_id",
    # Transport
    "Transport",
    # Exceptions
    "ConfigurationError",
]
