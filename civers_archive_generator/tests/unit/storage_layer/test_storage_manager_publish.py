"""Check concurrent publication and separate results for each backend."""

import asyncio
import logging
from pathlib import Path

import pytest

from configs.models import StorageConfig
from domain.artifacts import ArchiveBundle, ArtifactFile
from storage_layer import StorageManager
from storage_layer.storage_strategy import StorageResult, StorageStrategy
from storage_layer.strategy_registry import StorageStrategyRegistry

pytestmark = [pytest.mark.unit]


def _bundle():
    return ArchiveBundle(
        snapshot_id="req_1_20260901_120000",
        url="https://example.com/p",
        request_id="req-1",
        root=Path("/archives/example_com/p/req_1_20260901_120000"),
        files=(
            ArtifactFile(
                name="archive.warc",
                path=Path("/archives/example_com/p/req_1_20260901_120000/archive.warc"),
                size=100,
                media_type="application/warc",
                created=__import__("datetime").datetime(2026, 9, 1, 12, 0, 0),
            ),
        ),
    )


class RecordingBackend(StorageStrategy):
    """Records when it starts and stops, so overlap can be observed directly."""

    in_flight = 0
    max_in_flight = 0

    def __init__(self, **config):
        self.config = config
        self.seen = []

    async def store_artifacts(self, bundle):
        type(self).in_flight += 1
        type(self).max_in_flight = max(type(self).max_in_flight, type(self).in_flight)
        try:
            await asyncio.sleep(0.01)
            self.seen.append(bundle)
            return StorageResult(success=True, storage_type="whatever-i-claim", storage_location="loc")
        finally:
            type(self).in_flight -= 1


class ExplodingBackend(StorageStrategy):
    def __init__(self, **config):
        self.config = config

    async def store_artifacts(self, bundle):
        raise RuntimeError("backend on fire")


class FailingBackend(StorageStrategy):
    def __init__(self, **config):
        self.config = config

    async def store_artifacts(self, bundle):
        return StorageResult(success=False, storage_type="x", error_message="nope")


@pytest.fixture
def registry():
    """Register test backends for one test, then put the registry back."""
    before = dict(StorageStrategyRegistry._strategies)
    RecordingBackend.in_flight = 0
    RecordingBackend.max_in_flight = 0
    yield StorageStrategyRegistry
    StorageStrategyRegistry._strategies.clear()
    StorageStrategyRegistry._strategies.update(before)


def _manager(registry, **backends):
    for name, cls in backends.items():
        registry.register(name, cls)
    return StorageManager(
        StorageConfig(enabled=list(backends), backends={n: {} for n in backends})
    )


class TestFanOut:
    @pytest.mark.asyncio
    async def test_every_enabled_backend_is_called(self, registry):
        manager = _manager(registry, one=RecordingBackend, two=RecordingBackend)

        result = await manager.publish(_bundle())

        assert len(result.results) == 2
        assert manager.strategies["one"].seen and manager.strategies["two"].seen

    @pytest.mark.asyncio
    async def test_backends_run_concurrently(self, registry):
        """Observed overlap, not wall-clock timing."""
        manager = _manager(registry, one=RecordingBackend, two=RecordingBackend, three=RecordingBackend)

        await manager.publish(_bundle())

        assert RecordingBackend.max_in_flight == 3

    @pytest.mark.asyncio
    async def test_the_bundle_tells_each_backend_what_to_publish(self, registry):
        manager = _manager(registry, one=RecordingBackend)
        bundle = _bundle()

        await manager.publish(bundle)

        assert manager.strategies["one"].seen == [bundle], "the bundle arrives untouched"


class TestOneBackendCannotHarmAnother:
    @pytest.mark.asyncio
    async def test_a_raising_backend_does_not_stop_the_others(self, registry):
        manager = _manager(registry, boom=ExplodingBackend, fine=RecordingBackend)

        result = await manager.publish(_bundle())

        assert len(result.results) == 2
        assert manager.strategies["fine"].seen, "the healthy backend still ran"
        assert result.get_result_by_type("boom").success is False
        assert "backend on fire" in result.get_result_by_type("boom").error_message

    @pytest.mark.asyncio
    async def test_overall_success_needs_only_one_backend(self, registry):
        manager = _manager(registry, bad=FailingBackend, good=RecordingBackend)

        result = await manager.publish(_bundle())

        assert result.overall_success is True
        assert result.get_successful_backends() == ["good"]
        assert result.get_failed_backends() == ["bad"]

    @pytest.mark.asyncio
    async def test_all_failing_means_no_overall_success(self, registry):
        manager = _manager(registry, bad=FailingBackend, boom=ExplodingBackend)

        result = await manager.publish(_bundle())

        assert result.overall_success is False


class TestResultsAreLabelledByConfigKey:
    @pytest.mark.asyncio
    async def test_storage_type_comes_from_the_config_key(self, registry):
        """The backend claims 'whatever-i-claim'; the configured name is what counts."""
        manager = _manager(registry, civers_rest_api=RecordingBackend)

        result = await manager.publish(_bundle())

        assert [r.storage_type for r in result.results] == ["civers_rest_api"]

    @pytest.mark.asyncio
    async def test_a_raising_backend_is_still_labelled(self, registry):
        manager = _manager(registry, boom=ExplodingBackend)

        result = await manager.publish(_bundle())

        assert result.results[0].storage_type == "boom"


class TestNoBackends:
    @pytest.mark.asyncio
    async def test_publishing_with_none_enabled_is_quiet(self, caplog):
        """Local-disk-only is a supported mode, not an error."""
        manager = StorageManager(StorageConfig())

        with caplog.at_level(logging.DEBUG):
            result = await manager.publish(_bundle())

        assert result.results == []
        assert result.overall_success is False
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


class TestLoggingContract:
    @pytest.mark.asyncio
    async def test_a_failing_backend_is_warned_about(self, registry, caplog):
        manager = _manager(registry, bad=FailingBackend)

        with caplog.at_level(logging.DEBUG):
            await manager.publish(_bundle())

        assert [r for r in caplog.records if r.levelno >= logging.WARNING]

    @pytest.mark.asyncio
    async def test_a_successful_publish_warns_about_nothing(self, registry, caplog):
        manager = _manager(registry, good=RecordingBackend)

        with caplog.at_level(logging.DEBUG):
            await manager.publish(_bundle())

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
