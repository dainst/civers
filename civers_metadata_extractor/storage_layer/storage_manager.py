"""
Storage Manager - Multi-Backend Coordinator.

Coordinates storage operations across multiple enabled storage backends,
aggregating results and handling failures gracefully.
"""

from typing import Any

from configs.logging_config import get_logger
from configs.models import StorageConfig

from .storage_strategy import MultiStorageResult, StorageResult, StorageStrategy
from .strategy_registry import StorageStrategyRegistry


class StorageManager:
    """
    Multi-backend storage coordinator.

    Manages multiple storage backends simultaneously, storing metadata to
    all enabled backends and aggregating results. Provides graceful error
    handling and continues even if some backends fail.

    Attributes:
        storage_config: Storage configuration from app_config.yaml
        strategies: Dictionary mapping backend names to strategy instances
        logger: Logger instance for this manager

    Example:
        >>> storage_config = StorageConfig(
        ...     enabled=["local_file", "civers_rest_api"],
        ...     backends={
        ...         "local_file": {"base_path": "output/metadata"},
        ...         "civers_rest_api": {"upload_url": "http://localhost:8000/api/upload"}
        ...     }
        ... )
        >>> manager = StorageManager(storage_config)
        >>> result = await manager.store_metadata(
        ...     data={"test": "data"},
        ...     request_id="req_123",
        ...     url="https://example.com",
        ...     filename="metadata.json"
        ... )
        >>> print(result.overall_success)
        True
        >>> print(result.get_successful_backends())
        ['local_file', 'civers_rest_api']
    """

    def __init__(self, storage_config: StorageConfig):
        """
        Initialize Storage Manager with configuration.

        Args:
            storage_config: Configuration specifying enabled backends and their settings
        """
        self.storage_config = storage_config
        self.strategies: dict[str, StorageStrategy] = {}
        self.logger = get_logger(__name__)

        # Initialize all enabled storage strategies
        self._initialize_strategies()

    def _initialize_strategies(self) -> None:
        """
        Initialize strategy instances for all enabled backends.

        Reads enabled backends from config, retrieves strategy classes from
        registry, and creates instances with backend-specific configuration.
        Logs initialization and continues if some backends fail.
        """
        # Get enabled backends from storage configuration
        enabled = self.storage_config.get_enabled_backends()

        self.logger.info(f"Initializing {len(enabled)} storage backend(s): {', '.join(enabled)}")

        for backend_name in enabled:
            try:
                # Get backend configuration
                if backend_name not in self.storage_config.backends:
                    self.logger.warning(
                        f"⚠️ Backend '{backend_name}' is enabled but has no configuration. Skipping."
                    )
                    continue

                backend_config = self.storage_config.backends[backend_name]

                # Get strategy class from registry
                strategy_class = StorageStrategyRegistry.get_strategy_class(backend_name)

                # Create strategy instance
                strategy = self._create_strategy_instance(
                    strategy_class=strategy_class, backend_name=backend_name, config=backend_config
                )

                self.strategies[backend_name] = strategy
                self.logger.info(f"✅ Initialized storage backend: {backend_name}")

            except Exception as e:
                self.logger.error(
                    f"❌ Failed to initialize backend '{backend_name}': {e}. Continuing with other backends."
                )

    def _create_strategy_instance(
        self, strategy_class: type[StorageStrategy], backend_name: str, config: dict[str, Any]
    ) -> StorageStrategy:
        """
        Create a storage strategy instance with backend-specific configuration.

        Args:
            strategy_class: Class type to instantiate
            backend_name: Name of the backend (for logging/debugging)
            config: Backend-specific configuration dictionary

        Returns:
            Initialized storage strategy instance

        Raises:
            TypeError: If strategy_class cannot be instantiated with the config
        """
        # Create instance based on backend type
        if backend_name == "local_file":
            return strategy_class(  # type: ignore[call-arg]
                base_path=config.get("base_path", "output/metadata"),
                create_subdirectories=config.get("create_subdirectories", True),
            )

        elif backend_name == "civers_rest_api":
            return strategy_class(  # type: ignore[call-arg]
                upload_url=config["upload_url"],  # Required
                timeout_seconds=config.get("timeout_seconds", 30),
                retry_attempts=config.get("retry_attempts", 3),
                verify_ssl=config.get("verify_ssl", True),
                auth=config.get("auth"),
            )

        else:
            # Generic fallback - try passing config as kwargs
            try:
                return strategy_class(**config)
            except TypeError as e:
                raise TypeError(
                    f"Cannot create strategy for '{backend_name}' with provided config. Error: {e}"
                ) from e

    async def store_metadata(
        self, data: dict[str, Any], request_id: str, url: str, filename: str
    ) -> MultiStorageResult:
        """
        Store metadata to all enabled backends and aggregate results.

        Executes storage operations in parallel across all enabled backends.
        Checks availability before storing. Aggregates individual results
        into a MultiStorageResult. Continues even if some backends fail.

        Args:
            data: Metadata dictionary to store
            request_id: Request ID for tracking
            url: Original source URL
            filename: Filename for the metadata file

        Returns:
            MultiStorageResult containing individual results and overall status

        Example:
            >>> result = await manager.store_metadata(
            ...     data={"title": "Test"},
            ...     request_id="req_001",
            ...     url="https://example.com",
            ...     filename="metadata_req_001.json"
            ... )
            >>> if result.overall_success:
            ...     print(f"Stored to: {result.get_successful_backends()}")
        """
        results: list[StorageResult] = []
        backend_names = list(self.strategies.keys())

        self.logger.info(
            f"📦 Storing metadata to {len(backend_names)} backend(s): {', '.join(backend_names)}"
        )

        # Store to each backend
        for backend_name, strategy in self.strategies.items():
            try:
                # Check if backend is available
                is_available = await strategy.is_available()

                if not is_available:
                    self.logger.warning(f"⚠️ Backend '{backend_name}' is not available. Skipping.")
                    results.append(
                        StorageResult(
                            success=False,
                            storage_type=backend_name,
                            error_message="Backend not available",
                        )
                    )
                    continue

                # Store metadata
                result = await strategy.store_metadata(
                    data=data, request_id=request_id, url=url, filename=filename
                )

                results.append(result)

                if result.success:
                    self.logger.info(
                        f"✅ Successfully stored to '{backend_name}': {result.storage_location}"
                    )
                else:
                    self.logger.warning(
                        f"❌ Failed to store to '{backend_name}': {result.error_message}"
                    )

            except Exception as e:
                # Handle unexpected errors per backend
                error_msg = f"Unexpected error: {e}"
                self.logger.error(f"❌ Error storing to '{backend_name}': {error_msg}")
                results.append(
                    StorageResult(success=False, storage_type=backend_name, error_message=error_msg)
                )

        # Aggregate results
        successful_backends = [r.storage_type for r in results if r.success]
        failed_backends = [r.storage_type for r in results if not r.success]

        overall_success = len(successful_backends) > 0

        # Determine primary location (prefer local_file, then first successful)
        primary_location = None
        if overall_success:
            # Try to get local_file location first
            for result in results:
                if result.success and result.storage_type == "local_file":
                    primary_location = result.storage_location
                    break

            # If no local_file, use first successful
            if primary_location is None:
                for result in results:
                    if result.success:
                        primary_location = result.storage_location
                        break

        # Log summary
        if overall_success:
            self.logger.info(
                f"✅ Storage complete: {len(successful_backends)}/{len(results)} backends succeeded. "
                f"Successful: {', '.join(successful_backends)}"
            )
        else:
            self.logger.error(
                f"❌ All {len(results)} storage backends failed. "
                f"Failed: {', '.join(failed_backends)}"
            )

        return MultiStorageResult(
            overall_success=overall_success, results=results, primary_location=primary_location
        )

    def get_enabled_backends(self) -> list[str]:
        """
        Get list of enabled backend names.

        Returns:
            List of strategy keys that are currently initialized
        """
        return list(self.strategies.keys())

    def get_backend_strategy(self, backend_name: str) -> StorageStrategy:
        """
        Get strategy instance for a specific backend.

        Args:
            backend_name: Name of the backend (e.g., "local_file")

        Returns:
            Strategy instance for the backend

        Raises:
            KeyError: If backend is not initialized
        """
        if backend_name not in self.strategies:
            raise KeyError(
                f"Backend '{backend_name}' is not initialized. "
                f"Available backends: {', '.join(self.get_enabled_backends())}"
            )

        return self.strategies[backend_name]
