"""Result shapes and archive status returned by execute(ArchiveCommand)."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from archive_generators.archive_result import ArtifactResult, ArtifactStatus
from archive_services.archive_service import ArchiveService
from configs.models import DomainConfig
from domain.commands import ArchiveCommand
from storage_layer.storage_strategy import MultiStorageResult, StorageResult

from civers_common import ResultStatus

# What every transport may rely on being present.
SUCCESS_DATA_KEYS = {
    "request_id",
    "url",
    "archive_path",
    "artifacts_created",
    "failed_artifacts",
    "missing_artifacts",
    "skipped_generators",
    "processing_time_seconds",
    "snapshot_id",
}

FAILURE_DATA_KEYS = {
    "archive_path",
    "artifacts_created",
    "failed_artifacts",
    "missing_artifacts",
    "skipped_generators",
    "processing_time_seconds",
}


def _published(snapshot_id=None):
    results = []
    if snapshot_id:
        results.append(
            StorageResult(
                success=True,
                storage_type="civers_rest_api",
                storage_location=snapshot_id,
            )
        )
    return MultiStorageResult(overall_success=bool(results), results=results)


@pytest.fixture
def service(sample_config):
    return ArchiveService(sample_config)


def _stub_generator(artifacts):
    async def capture(url, output_folder, requested):
        results = []
        for artifact in artifacts:
            if artifact.status is ArtifactStatus.SUCCESS:
                path = Path(output_folder) / Path(artifact.file_path).name
                path.write_bytes(b"synthetic capture")
                artifact = replace(
                    artifact, file_path=str(path), file_size=path.stat().st_size
                )
            results.append(artifact)
        return results

    return Mock(
        generate_archive=AsyncMock(side_effect=capture),
        get_generator_name=Mock(return_value="scoop"),
        get_capabilities=Mock(return_value=["warc", "screenshot"]),
    )


def _run(service, artifacts, published=None):
    """Run the workflow with controlled capture and publication results."""
    service.generator_factory = Mock()
    service.generator_factory.create_generators.side_effect = lambda domain: [
        (domain.generators[0], _stub_generator(artifacts))
    ]

    return patch.multiple(
        service,
        url_guard=Mock(validate=AsyncMock()),
        storage=Mock(
            publish=AsyncMock(
                return_value=published if published is not None else _published()
            )
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestSuccess:
    async def test_data_holds_exactly_the_agreed_keys(self, service):
        with _run(
            service,
            [
                ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100),
                ArtifactResult("screenshot", ArtifactStatus.SUCCESS, "/tmp/s.png", 50),
            ],
        ):
            result = await service.execute(
                ArchiveCommand(request_id="req-1", url="https://example.com/p")
            )

        assert result.success_status is ResultStatus.COMPLETE
        assert set(result.data) == SUCCESS_DATA_KEYS
        assert result.data["request_id"] == "req-1"
        assert result.data["url"] == "https://example.com/p"
        assert result.data["artifacts_created"] == ["warc", "screenshot"]
        assert Path(result.data["archive_path"]).is_dir()
        assert isinstance(result.data["processing_time_seconds"], float)


@pytest.mark.unit
@pytest.mark.asyncio
class TestFailure:
    async def test_a_failed_generator_reports_the_agreed_keys(self, service):
        with _run(
            service, [ArtifactResult("warc", ArtifactStatus.FAILED, None, 0, "boom")]
        ):
            result = await service.execute(
                ArchiveCommand(request_id="req-3", url="https://example.com/p")
            )

        assert result.success_status is ResultStatus.FAILED
        assert result.error_type == "archive_generation_failed"
        assert result.error
        assert set(result.data) == FAILURE_DATA_KEYS

    async def test_a_requested_artifact_nobody_reported_is_missing(self, service):
        """example.com asks for warc and screenshot; nothing reported on screenshot at all."""
        with _run(
            service, [ArtifactResult("warc", ArtifactStatus.FAILED, None, 0, "boom")]
        ):
            result = await service.execute(
                ArchiveCommand(request_id="req-m", url="https://example.com/p")
            )

        assert result.data["missing_artifacts"] == ["screenshot"]
        assert result.data["failed_artifacts"] == ["warc"]

    async def test_a_disabled_domain_is_a_configuration_problem_not_a_processing_one(
        self, sample_config, tmp_path
    ):
        """Return configuration_not_found when a configured domain is disabled."""
        sample_config.app.archive_directory = str(tmp_path / "archives")
        sample_config.domains[0].enabled = False
        service = ArchiveService(sample_config)

        result = await service.execute(
            ArchiveCommand(request_id="req-d", url="https://example.com/p")
        )

        assert result.error_type == "configuration_not_found"
        assert result.error_type != "processing_error", "would be retried forever"
        assert "disabled" in result.error
        assert set(result.data) == FAILURE_DATA_KEYS

    async def test_a_disabled_wildcard_domain_is_refused_the_same_way(
        self, sample_config, tmp_path
    ):
        """Wildcards are a separate branch of resolve_domain with its own disabled check."""
        sample_config.app.archive_directory = str(tmp_path / "archives")
        sample_config.domains.append(
            DomainConfig(
                name="*.wild.org",
                generators=[{"name": "scoop", "artifacts": ["warc"]}],
                webpage_types="dynamic",
                enabled=False,
            )
        )
        service = ArchiveService(sample_config)

        result = await service.execute(
            ArchiveCommand(request_id="req-w", url="https://a.wild.org/p")
        )

        assert result.error_type == "configuration_not_found"
        assert "disabled" in result.error

    async def test_a_disabled_domain_never_starts_a_capture(
        self, sample_config, tmp_path
    ):
        """Nothing should be written for a domain that was turned off."""
        archives = tmp_path / "archives"
        sample_config.app.archive_directory = str(archives)
        sample_config.domains[0].enabled = False
        service = ArchiveService(sample_config)
        service.generator_factory = Mock()

        await service.execute(
            ArchiveCommand(request_id="req-d", url="https://example.com/p")
        )

        service.generator_factory.create_generators.assert_not_called()
        assert not archives.exists(), "no archive folder for a disabled domain"

    async def test_an_unconfigured_domain_never_reaches_the_generators(self, service):
        result = await service.execute(
            ArchiveCommand(request_id="req-2", url="https://nope.invalid/p")
        )

        assert result.success_status is ResultStatus.FAILED
        assert result.error_type == "configuration_not_found"
        assert set(result.data) == FAILURE_DATA_KEYS
        json.dumps(result.data)


@pytest.mark.unit
@pytest.mark.asyncio
class TestSnapshotIdPrecedence:
    async def test_the_backend_id_wins(self, service):
        with _run(
            service,
            [ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100)],
            published=_published("snap-rest-42"),
        ):
            result = await service.execute(
                ArchiveCommand(request_id="req-snap", url="https://example.com/p")
            )

        assert result.data["snapshot_id"] == "snap-rest-42"

    async def test_otherwise_the_local_folder_name_stands(self, service):
        with _run(
            service,
            [ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100)],
        ):
            result = await service.execute(
                ArchiveCommand(request_id="req-local", url="https://example.com/p")
            )

        assert result.data["snapshot_id"].startswith("req_req-local_")


@pytest.mark.unit
@pytest.mark.asyncio
class TestPartialArchives:
    """Check partial captures against the artifacts requested in configuration."""

    async def _archive(self, service, artifacts, generators=None):
        service.generator_factory = Mock()
        service.generator_factory.create_generators.side_effect = lambda domain: (
            [(domain.generators[0], g) for g in generators]
            if generators is not None
            else [(domain.generators[0], _stub_generator(artifacts))]
        )
        with patch.multiple(
            service,
            url_guard=Mock(validate=AsyncMock()),
            storage=Mock(publish=AsyncMock(return_value=_published())),
        ):
            return await service.execute(
                ArchiveCommand(request_id="req-p", url="https://example.com/p")
            )

    async def test_a_silently_dropped_artifact_is_reported(self, service):
        """Report a missing screenshot when the generator returns only WARC."""
        result = await self._archive(
            service,
            [ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100)],
        )

        assert result.success_status is ResultStatus.PARTIAL
        assert result.data["missing_artifacts"] == ["screenshot"]
        assert result.data["artifacts_created"] == ["warc"]

    async def test_a_generator_that_could_not_run_is_reported(self, service):
        """The config names scoop; no configured generator was available."""
        result = await self._archive(service, [], generators=[])

        assert result.success_status is ResultStatus.FAILED, (
            "nothing was captured at all"
        )
        assert result.error_type == "missing_required_artifacts"
        assert result.data["skipped_generators"] == ["scoop"]
        assert result.data["missing_artifacts"] == ["warc", "screenshot"]

    async def test_a_complete_archive_says_so(self, service):
        result = await self._archive(
            service,
            [
                ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100),
                ArtifactResult("screenshot", ArtifactStatus.SUCCESS, "/tmp/s.png", 50),
            ],
        )

        assert result.success_status is ResultStatus.COMPLETE
        assert result.data["missing_artifacts"] == []
        assert result.data["failed_artifacts"] == []
        assert result.data["skipped_generators"] == []

    async def test_a_partly_failed_capture_is_partial_not_a_write_off(self, service):
        result = await self._archive(
            service,
            [
                ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100),
                ArtifactResult("screenshot", ArtifactStatus.FAILED, None, 0, "boom"),
            ],
        )

        assert result.success_status is ResultStatus.PARTIAL
        assert result.data["failed_artifacts"] == ["screenshot"]


@pytest.mark.unit
@pytest.mark.asyncio
class TestWhatReachesTheBusSurvivesSerialisation:
    """Check JSON serialization of results from complete, partial and failed captures."""

    ALL_SUCCEEDED = (
        ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100),
        ArtifactResult("screenshot", ArtifactStatus.SUCCESS, "/tmp/s.png", 50),
    )
    ONE_SILENTLY_ABSENT = (
        ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 100),
    )
    NOTHING_PRODUCED = (ArtifactResult("warc", ArtifactStatus.FAILED, None, 0, "boom"),)

    async def _real_result(self, service, artifacts, url="https://example.com/p"):
        with _run(service, artifacts):
            return await service.execute(ArchiveCommand(request_id="req-json", url=url))

    @pytest.mark.parametrize(
        "case", ["ALL_SUCCEEDED", "ONE_SILENTLY_ABSENT", "NOTHING_PRODUCED"]
    )
    async def test_the_data_of_a_real_run_serialises(self, service, case):
        result = await self._real_result(service, getattr(self, case))

        json.dumps(result.data)
