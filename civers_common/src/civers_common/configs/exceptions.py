"""Shared configuration exceptions for CiVers services."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid or a lookup fails.

    The canonical config error across CiVers services; subclass it for a more specific
    hierarchy.
    """
