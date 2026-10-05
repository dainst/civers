"""Publish archive bundles to configured storage backends."""

import asyncio
from dataclasses import replace
from typing import Dict, Any, List

from configs.models import StorageConfig
from configs.logging_config import get_logger
from .storage_strategy import StorageStrategy, StorageResult, MultiStorageResult
from .strategy_registry import StorageStrategyRegistry
from domain.artifacts import ArchiveBundle


class StorageManager:
    """Build enabled backends, skip invalid ones and publish to them concurrently."""
    
    def __init__(self, storage_config: StorageConfig):
        """Build a strategy instance for every enabled backend."""
        self.storage_config = storage_config
        self.strategies: Dict[str, StorageStrategy] = {}
        self.logger = get_logger(__name__)
        
        self._initialize_strategies()
    
    def _initialize_strategies(self) -> None:
        """Build enabled backends; log and skip missing or invalid configuration."""
        enabled = self.storage_config.get_enabled_backends()

        if not enabled:
            self.logger.info("No storage backend enabled — artifacts stay on local disk only")
            return

        self.logger.info(f"Initializing {len(enabled)} storage backend(s): {', '.join(enabled)}")
        
        for backend_name in enabled:
            try:
                # A shared config tree may name backends only another service implements.
                if not StorageStrategyRegistry.is_registered(backend_name):
                    self.logger.info(
                        f"Backend '{backend_name}' is not implemented by this service. Skipping."
                    )
                    continue

                if backend_name not in self.storage_config.backends:
                    self.logger.warning(
                        f"⚠️ Backend '{backend_name}' is enabled but has no configuration. Skipping."
                    )
                    continue
                
                backend_config = self.storage_config.backends[backend_name]
                
                strategy_class = StorageStrategyRegistry.get_strategy_class(backend_name)
                
                strategy = self._create_strategy_instance(
                    strategy_class=strategy_class,
                    config=backend_config,
                )
                
                self.strategies[backend_name] = strategy
                self.logger.info(f"✅ Initialized storage backend: {backend_name}")
                
            except Exception as e:
                self.logger.error(
                    f"❌ Failed to initialize backend '{backend_name}': {e}. Continuing with other backends."
                )
    
    def _create_strategy_instance(
        self,
        strategy_class: type[StorageStrategy],
        config: Dict[str, Any],
    ) -> StorageStrategy:
        """Build a backend using its from_config method."""
        return strategy_class.from_config(config)
    
    def get_enabled_backends(self) -> List[str]:
        """Return the config keys of the backends that were successfully built."""
        return list(self.strategies.keys())
    
    def get_backend_strategy(self, backend_name: str) -> StorageStrategy:
        """Return the strategy registered under a config key.

        Raises:
            KeyError: No such backend was initialized.
        """
        if backend_name not in self.strategies:
            raise KeyError(
                f"Backend '{backend_name}' is not initialized. "
                f"Available backends: {', '.join(self.get_enabled_backends())}"
            )
        
        return self.strategies[backend_name]
    
    async def publish(self, bundle: ArchiveBundle) -> MultiStorageResult:
        """Publish the bundle concurrently and collect results under configured backend names.

        Each backend selects its files. Backend errors become failed results.
        """
        if not self.strategies:
            self.logger.debug("No storage backend enabled — nothing to publish")
            return MultiStorageResult(overall_success=False, results=[])

        names = list(self.strategies)
        self.logger.info(
            f"📦 Publishing {bundle.snapshot_id} to {len(names)} backend(s): {', '.join(names)}"
        )

        outcomes = await asyncio.gather(
            *(self.strategies[name].store_artifacts(bundle) for name in names),
            return_exceptions=True,
        )

        results = [self._label(name, outcome) for name, outcome in zip(names, outcomes)]
        return MultiStorageResult(
            overall_success=any(r.success for r in results),
            results=results,
        )

    def _label(self, backend_name: str, outcome) -> StorageResult:
        """Use the configured backend name in successful and failed results."""
        if isinstance(outcome, BaseException):
            self.logger.error(f"❌ Error publishing to '{backend_name}': {outcome}")
            return StorageResult(
                success=False,
                storage_type=backend_name,
                error_message=f"Unexpected error: {outcome}",
            )

        if outcome.success:
            self.logger.info(f"✅ Published to {backend_name}: {outcome.storage_location}")
        else:
            self.logger.warning(f"⚠️ Publishing failed for {backend_name}: {outcome.error_message}")

        return replace(outcome, storage_type=backend_name)
