"""Check storage backend registration, lookup and missing-name errors."""

import pytest
from storage_layer.storage_strategy import StorageResult, StorageStrategy
from storage_layer.strategy_registry import StorageStrategyRegistry

pytestmark = [pytest.mark.unit]


class Pretend(StorageStrategy):
    async def store_artifacts(self, bundle) -> StorageResult:
        return StorageResult(success=True, storage_type="pretend")


@pytest.fixture
def registry():
    """Give each test a clean registry, then put the real one back."""
    before = dict(StorageStrategyRegistry._strategies)
    StorageStrategyRegistry.clear_registry()
    yield StorageStrategyRegistry
    StorageStrategyRegistry._strategies.clear()
    StorageStrategyRegistry._strategies.update(before)


class TestRegistering:
    def test_a_registered_backend_can_be_fetched(self, registry):
        registry.register("pretend", Pretend)

        assert registry.is_registered("pretend")
        assert registry.get_strategy_class("pretend") is Pretend

    def test_an_unregistered_name_is_not_registered(self, registry):
        assert registry.is_registered("nope") is False

    def test_a_class_that_is_not_a_strategy_is_refused(self, registry):
        class NotAStrategy:
            pass

        with pytest.raises(TypeError, match="must inherit from StorageStrategy"):
            registry.register("bad", NotAStrategy)


class TestFetchingSomethingMissing:
    def test_the_error_names_what_is_available(self, registry):
        registry.register("pretend", Pretend)

        with pytest.raises(ValueError, match="'pretend'"):
            registry.get_strategy_class("s3")

    def test_the_error_is_readable_with_nothing_registered(self, registry):
        with pytest.raises(ValueError, match="none"):
            registry.get_strategy_class("s3")
