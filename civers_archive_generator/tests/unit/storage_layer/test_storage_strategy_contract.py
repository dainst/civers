"""Check the required store_artifacts method and backend construction."""

from pathlib import Path
from typing import Any

import pytest
from configs.models import StorageConfig
from domain.artifacts import ArchiveBundle
from storage_layer import StorageManager
from storage_layer.storage_strategy import StorageResult, StorageStrategy
from storage_layer.strategy_registry import StorageStrategyRegistry

pytestmark = [pytest.mark.unit]


class OnlyStoresArtifacts(StorageStrategy):
    """A backend that implements the one thing the contract asks for."""

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.calls: list[ArchiveBundle] = []

    async def store_artifacts(self, bundle: ArchiveBundle) -> StorageResult:
        self.calls.append(bundle)
        return StorageResult(
            success=True, storage_type="fake", storage_location="somewhere"
        )


@pytest.fixture
def registered_fake():
    """Register the fake backend for the duration of one test."""
    StorageStrategyRegistry.register("fake", OnlyStoresArtifacts)
    yield "fake"
    StorageStrategyRegistry._strategies.pop("fake", None)


class TestTheContractIsWhatCallersActuallyUse:
    def test_omitting_store_artifacts_is_refused_at_construction(self):
        """A backend missing the only method that matters must not construct at all."""

        class ForgotTheOnlyMethod(StorageStrategy):
            pass

        with pytest.raises(TypeError, match="store_artifacts"):
            ForgotTheOnlyMethod()

    @pytest.mark.asyncio
    async def test_the_manager_really_calls_it(self, registered_fake):
        manager = StorageManager(
            StorageConfig(enabled=[registered_fake], backends={registered_fake: {}})
        )

        await manager.publish(
            ArchiveBundle(
                snapshot_id="req_1",
                url="https://example.com/p",
                request_id="req-1",
                root=Path("/archives/example_com/p/req_1"),
            )
        )

        backend = manager.strategies[registered_fake]
        assert [b.request_id for b in backend.calls] == ["req-1"]
        assert [str(b.root) for b in backend.calls] == ["/archives/example_com/p/req_1"]

    def test_from_config_stays_the_construction_hook(self, registered_fake):
        backend = OnlyStoresArtifacts.from_config(
            {"upload_url": "http://example.invalid"}
        )

        assert backend.config == {"upload_url": "http://example.invalid"}
