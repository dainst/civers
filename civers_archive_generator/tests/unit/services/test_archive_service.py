"""Exercise the command workflow with real workspace, metadata and artifact files."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from archive_generators.archive_result import ArtifactResult, ArtifactStatus
from archive_services.archive_metadata import ArchiveMetadata
from archive_services.archive_service import ArchiveService
from domain.commands import ArchiveCommand
from storage_layer.storage_strategy import MultiStorageResult, StorageResult

from civers_common import ResultStatus

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def archive_service(sample_config):
    return ArchiveService(sample_config)


@pytest.fixture
def capture_generator(archive_service, monkeypatch):
    """Replace browser capture, leaving the file and publication workflow intact."""
    filenames = {"warc": "archive.warc", "screenshot": "screenshot.png"}

    async def capture(url, output_folder, requested):
        folder = Path(output_folder)
        (folder / "scoop_stdout.log").write_text("capture finished", encoding="utf-8")
        results = []
        for name in requested:
            path = folder / filenames[name]
            path.write_bytes(b"synthetic capture")
            results.append(
                ArtifactResult(
                    name, ArtifactStatus.SUCCESS, str(path), path.stat().st_size
                )
            )
        return results

    generator = Mock(
        generate_archive=AsyncMock(side_effect=capture),
        get_generator_name=Mock(return_value="scoop"),
        get_capabilities=Mock(return_value=["warc", "screenshot"]),
    )
    monkeypatch.setattr(
        archive_service.generator_factory,
        "create_generators",
        Mock(side_effect=lambda domain: [(domain.generators[0], generator)]),
    )
    monkeypatch.setattr(archive_service.url_guard, "validate", AsyncMock())
    return generator


async def test_command_publishes_capture_files_and_metadata(
    archive_service, capture_generator, monkeypatch
):
    publish = AsyncMock(
        return_value=MultiStorageResult(overall_success=False, results=[])
    )
    monkeypatch.setattr(archive_service.storage, "publish", publish)
    command = ArchiveCommand(request_id="req-files", url="https://example.com/p")

    result = await archive_service.execute(command)

    assert result.success_status is ResultStatus.COMPLETE, result.error
    folder = result.data["archive_path"]
    capture_generator.generate_archive.assert_awaited_once_with(
        command.url, folder, ["warc", "screenshot"]
    )
    assert isinstance(folder, str)
    bundle = publish.await_args.args[0]
    assert bundle.root == Path(folder)
    assert bundle.request_id == command.request_id
    assert bundle.url == command.url
    assert bundle.snapshot_id == result.data["snapshot_id"] == Path(folder).name
    assert {file.name for file in bundle.files} == {
        "archive.warc",
        "screenshot.png",
        "scoop_stdout.log",
        ArchiveMetadata.FILENAME,
    }
    assert all(
        file.path.is_file() and file.size == file.path.stat().st_size
        for file in bundle.files
    )

    metadata = json.loads(
        (Path(folder) / ArchiveMetadata.FILENAME).read_text(encoding="utf-8")
    )
    assert metadata["archive_info"]["request_id"] == command.request_id
    assert metadata["archive_info"]["url"] == command.url
    assert metadata["artifacts_created"] == ["warc", "screenshot"]
    assert {file["name"] for file in metadata["files"]} == {
        "archive.warc",
        "screenshot.png",
        "scoop_stdout.log",
    }


async def test_processing_time_includes_publication(
    archive_service, capture_generator, monkeypatch
):
    started = datetime(2026, 10, 5, 12)  # noqa: DTZ001 - match the service's local clock
    clock = Mock(now=Mock(return_value=started))
    monkeypatch.setattr("archive_services.archive_service.datetime", clock)

    async def publish(bundle):
        clock.now.return_value = started + timedelta(seconds=7)
        return MultiStorageResult(overall_success=False, results=[])

    monkeypatch.setattr(archive_service.storage, "publish", publish)

    result = await archive_service.execute(
        ArchiveCommand(request_id="req-time", url="https://example.com/p")
    )

    assert result.success_status is ResultStatus.COMPLETE
    assert result.data["processing_time_seconds"] == 7.0


@pytest.mark.parametrize(
    "raises", [False, True], ids=["backend-failure", "publication-exception"]
)
async def test_storage_failure_preserves_local_capture(
    archive_service, capture_generator, monkeypatch, raises
):
    failed = MultiStorageResult(
        overall_success=False,
        results=[
            StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message="upload rejected",
            )
        ],
    )
    publish = AsyncMock(
        return_value=failed,
        side_effect=RuntimeError("storage unavailable") if raises else None,
    )
    monkeypatch.setattr(archive_service.storage, "publish", publish)

    result = await archive_service.execute(
        ArchiveCommand(request_id="req-storage", url="https://example.com/p")
    )

    assert result.success_status is ResultStatus.COMPLETE, result.error
    folder = Path(result.data["archive_path"])
    assert (folder / "archive.warc").is_file()
    assert (folder / ArchiveMetadata.FILENAME).is_file()
    assert result.data["snapshot_id"] == folder.name


async def test_generator_exception_returns_a_failed_result(
    archive_service, capture_generator
):
    capture_generator.generate_archive.side_effect = RuntimeError("capture crashed")

    result = await archive_service.execute(
        ArchiveCommand(request_id="req-crash", url="https://example.com/p")
    )

    assert result.success_status is ResultStatus.FAILED
    assert result.error_type == "archive_generation_failed"
    assert "capture crashed" in result.error
    assert result.data["artifacts_created"] == []


async def test_unexpected_error_is_returned_to_the_command_caller(
    archive_service, capture_generator
):
    archive_service.generator_factory.create_generators.side_effect = RuntimeError(
        "factory failed"
    )

    result = await archive_service.execute(
        ArchiveCommand(request_id="req-error", url="https://example.com/p")
    )

    assert result.success_status is ResultStatus.FAILED
    assert result.error_type == "processing_error"
    assert "factory failed" in result.error


async def test_cancellation_propagates_to_the_command_caller(
    archive_service, capture_generator
):
    capture_generator.generate_archive.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await archive_service.execute(
            ArchiveCommand(request_id="req-cancel", url="https://example.com/p")
        )


@pytest.mark.parametrize("protection_enabled", [True, False])
async def test_url_guard_controls_whether_capture_starts(
    archive_service, capture_generator, protection_enabled
):
    archive_service.config.app.ssrf_protection_enabled = protection_enabled
    archive_service.url_guard.validate.side_effect = ValueError("private address")

    result = await archive_service.execute(
        ArchiveCommand(request_id="req-guard", url="https://example.com/p")
    )

    if protection_enabled:
        assert result.success_status is ResultStatus.FAILED
        assert result.error_type == "ssrf_blocked"
        archive_service.url_guard.validate.assert_awaited_once_with(
            "https://example.com/p"
        )
        capture_generator.generate_archive.assert_not_awaited()
        assert not Path(archive_service.config.app.archive_directory).exists()
    else:
        assert result.success_status is ResultStatus.COMPLETE, result.error
        archive_service.url_guard.validate.assert_not_awaited()
        capture_generator.generate_archive.assert_awaited_once()
