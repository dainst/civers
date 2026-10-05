"""Construction and persistence of the archive's record."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from archive_generators.archive_result import ArtifactResult, ArtifactStatus
from archive_services.archive_metadata import ArchiveMetadata
from domain.artifacts import ArchiveBundle, ArtifactFile

STARTED = datetime(2026, 8, 31, 12, 0, 0)  # noqa: DTZ001 - metadata uses local timestamps


def _artifact(name, size=10, media_type="application/warc"):
    return ArtifactFile(
        name=name,
        path=Path("/nowhere") / name,
        size=size,
        media_type=media_type,
        created=datetime(2026, 8, 31, 12, 0, 30),  # noqa: DTZ001 - same local timestamp convention
    )


def _bundle(*files, root="/nowhere"):
    return ArchiveBundle(
        snapshot_id="req_1_20260831_120000",
        url="https://example.com",
        request_id="req-1",
        root=Path(root),
        files=files,
    )


def _build(bundle=None, artifacts=(), processing_time=22.5, generator_info=None):
    return ArchiveMetadata().build(
        bundle if bundle is not None else _bundle(),
        list(artifacts),
        STARTED,
        processing_time,
        generator_info=generator_info,
    )


@pytest.mark.unit
class TestBuild:
    def test_splits_successful_and_failed_artifacts(self):
        artifacts = [
            ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 10),
            ArtifactResult("screenshot", ArtifactStatus.FAILED, None, 0, "boom"),
        ]
        generator_info = [{"name": "singlefile", "capabilities": "singlefile"}]

        metadata = _build(artifacts=artifacts, generator_info=generator_info)

        assert metadata["artifacts_created"] == ["warc"]
        assert metadata["failed_artifacts"] == ["screenshot"]
        assert metadata["generator_info"] == generator_info

    def test_identity_comes_from_the_bundle(self):
        metadata = _build()

        assert metadata["archive_info"]["url"] == "https://example.com"
        assert metadata["archive_info"]["request_id"] == "req-1"

    def test_touches_no_filesystem(self):
        """The workspace already looked; building the record must not look again."""
        bundle = _bundle(_artifact("archive.warc"), root="/definitely/not/here")

        metadata = _build(bundle)

        assert not Path("/definitely/not/here").exists()
        assert [f["name"] for f in metadata["files"]] == ["archive.warc"]

    def test_files_keep_their_established_shape(self):
        bundle = _bundle(_artifact("archive.warc", size=1417660))

        metadata = _build(bundle)

        assert metadata["files"] == [
            {
                "name": "archive.warc",
                "size": 1417660,
                "created": "2026-08-31T12:00:30",
            }
        ]

    def test_lists_every_file_the_bundle_carries(self):
        bundle = _bundle(
            _artifact("archive.warc"),
            _artifact("screenshot.png", media_type="image/png"),
            _artifact("scoop_stdout.log", media_type="text/plain"),
        )

        metadata = _build(bundle)

        assert [f["name"] for f in metadata["files"]] == [
            "archive.warc",
            "screenshot.png",
            "scoop_stdout.log",
        ]

    def test_processing_time_is_the_value_it_was_given(self):
        """No internal clock — the caller decides what this number means."""
        metadata = _build(processing_time=22.222196)

        assert metadata["archive_info"]["processing_time_seconds"] == 22.222196

    def test_timestamps_agree_with_that_number(self):
        metadata = _build(processing_time=30.0)

        info = metadata["archive_info"]
        assert info["created_at"] == "2026-08-31T12:00:00"
        assert info["completed_at"] == "2026-08-31T12:00:30"

    def test_is_json_serialisable(self):
        bundle = _bundle(_artifact("archive.warc"))

        json.dumps(_build(bundle))


@pytest.mark.unit
@pytest.mark.asyncio
class TestSave:
    async def test_writes_metadata_json(self, tmp_path):
        await ArchiveMetadata().save(
            {"archive_info": {"url": "https://ex.com/ü"}}, str(tmp_path)
        )

        written = json.loads(
            (tmp_path / "archive_generator_metadata.json").read_text(encoding="utf-8")
        )
        assert written["archive_info"]["url"] == "https://ex.com/ü"

    async def test_keeps_unicode_readable_and_indents(self, tmp_path):
        await ArchiveMetadata().save({"url": "https://ex.com/ü"}, str(tmp_path))

        raw = (tmp_path / "archive_generator_metadata.json").read_text(encoding="utf-8")
        assert "ü" in raw, "ensure_ascii=False keeps the character itself"
        assert "\n  " in raw, "indent=2"
