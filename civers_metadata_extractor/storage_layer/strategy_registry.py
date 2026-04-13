"""
Storage Strategy Registry.

Provides a centralized registry for discovering and retrieving storage
strategy implementations. Enables the plugin architecture for easily
adding new storage backends without modifying core code.
"""

from .storage_strategy import StorageStrategy


class StorageStrategyRegistry:
    """
    Registry for storage strategy implementations.

    Uses the Registry pattern to manage available storage backends.
    Strategies are registered by name and can be retrieved dynamically.

    This enables:
    - Plugin architecture for new backends
    - Centralized discovery of available strategies
    - Type-safe retrieval of strategy classes
    - Better error messages when strategies are missing

    Example:
        >>> # Register a strategy
        >>> StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        >>>
        >>> # Check if registered
        >>> if StorageStrategyRegistry.is_registered("local_file"):
        ...     strategy_class = StorageStrategyRegistry.get_strategy_class("local_file")
        ...     strategy = strategy_class(base_path="output/metadata")
        >>>
        >>> # List all available
        >>> available = StorageStrategyRegistry.list_available()
        >>> print(available)
        ['local_file', 'civers_rest_api']
    """

    # Class-level dictionary mapping strategy names to classes
    _strategies: dict[str, type[StorageStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: type[StorageStrategy]) -> None:
        """
        Register a storage strategy implementation.

        Args:
            name: Unique identifier for the strategy (e.g., "local_file", "s3")
            strategy_class: Class that implements StorageStrategy interface

        Raises:
            TypeError: If strategy_class doesn't inherit from StorageStrategy

        Example:
            >>> StorageStrategyRegistry.register("s3", S3StorageStrategy)
        """
        if not issubclass(strategy_class, StorageStrategy):
            raise TypeError(
                f"Strategy class must inherit from StorageStrategy. Got: {strategy_class.__name__}"
            )

        cls._strategies[name] = strategy_class

    @classmethod
    def get_strategy_class(cls, name: str) -> type[StorageStrategy]:
        """
        Retrieve a registered storage strategy class by name.

        Args:
            name: Strategy identifier (e.g., "local_file")

        Returns:
            The strategy class type

        Raises:
            ValueError: If strategy name is not registered

        Example:
            >>> strategy_class = StorageStrategyRegistry.get_strategy_class("local_file")
            >>> strategy = strategy_class(base_path="output")
        """
        if name not in cls._strategies:
            available = cls.list_available()
            available_str = ", ".join(f"'{s}'" for s in available) if available else "none"
            raise ValueError(
                f"Unknown storage strategy: '{name}'. Available strategies: {available_str}"
            )

        return cls._strategies[name]

    @classmethod
    def list_available(cls) -> list[str]:
        """
        Get list of all registered strategy names.

        Returns:
            List of strategy identifiers

        Example:
            >>> strategies = StorageStrategyRegistry.list_available()
            >>> print(strategies)
            ['local_file', 'civers_rest_api']
        """
        return list(cls._strategies.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a strategy is registered.

        Args:
            name: Strategy identifier to check

        Returns:
            True if strategy is registered, False otherwise

        Example:
            >>> if StorageStrategyRegistry.is_registered("s3"):
            ...     print("S3 storage is available")
        """
        return name in cls._strategies

    @classmethod
    def clear_registry(cls) -> None:
        """
        Clear all registered strategies.

        WARNING: This is primarily for testing purposes.
        Use with caution in production code.
        """
        cls._strategies.clear()
