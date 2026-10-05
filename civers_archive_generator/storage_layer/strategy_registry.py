"""Register storage backend classes by their configuration names."""

from typing import Dict, Type
from .storage_strategy import StorageStrategy


class StorageStrategyRegistry:
    """Maps a backend name to the strategy class that implements it."""
    
    _strategies: Dict[str, Type[StorageStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[StorageStrategy]) -> None:
        """Register a strategy class under a config key.

        Raises:
            TypeError: The class does not inherit from StorageStrategy.
        """
        if not issubclass(strategy_class, StorageStrategy):
            raise TypeError(
                f"Strategy class must inherit from StorageStrategy. "
                f"Got: {strategy_class.__name__}"
            )
        
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get_strategy_class(cls, name: str) -> Type[StorageStrategy]:
        """Return the strategy class registered under a name.

        Raises:
            ValueError: The name was never registered.
        """
        if name not in cls._strategies:
            available = list(cls._strategies)
            available_str = ", ".join(f"'{s}'" for s in available) if available else "none"
            raise ValueError(
                f"Unknown storage strategy: '{name}'. "
                f"Available strategies: {available_str}"
            )
        
        return cls._strategies[name]
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Return True if a strategy is registered under this name."""
        return name in cls._strategies
    
    @classmethod
    def clear_registry(cls) -> None:
        """Remove every registration (test helper)."""
        cls._strategies.clear()
