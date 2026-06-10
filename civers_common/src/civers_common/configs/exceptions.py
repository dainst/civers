"""Shared configuration exceptions for CiVers services."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid or a lookup fails.

    This is the canonical exception for all config-related errors
    across CiVers services. Services may subclass this if they need
    a more specific exception hierarchy.
    """
