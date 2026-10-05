"""Check saved file records and immutable archive bundles."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.artifacts import ArchiveBundle, ArtifactFile


def _file(name="archive.warc", size=100, media_type="application/warc"):
    return ArtifactFile(
        name=name,
        path=Path("/archives/example_com/req_1") / name,
        size=size,
        media_type=media_type,
        created=datetime(2026, 8, 31, 12, 0, 0),
    )


def _bundle(*files):
    return ArchiveBundle(
        snapshot_id="req_1_20260831_120000",
        url="https://example.com/p",
        request_id="req-1",
        root=Path("/archives/example_com/req_1"),
        files=tuple(files),
    )


@pytest.mark.unit
class TestArtifactFile:
    def test_carries_the_five_facts_a_consumer_needs(self):
        f = _file()

        assert f.name == "archive.warc"
        assert f.path == Path("/archives/example_com/req_1/archive.warc")
        assert f.size == 100
        assert f.media_type == "application/warc"
        assert f.created == datetime(2026, 8, 31, 12, 0, 0)

    def test_is_frozen(self):
        f = _file()

        with pytest.raises(ValidationError):
            f.size = 999

    def test_model_dump_is_json_serialisable_with_path_as_string(self):
        payload = json.dumps(_file().model_dump(mode="json"))

        assert json.loads(payload) == {
            "name": "archive.warc",
            "path": "/archives/example_com/req_1/archive.warc",
            "size": 100,
            "media_type": "application/warc",
            "created": "2026-08-31T12:00:00",
        }


@pytest.mark.unit
class TestArchiveBundle:
    def test_carries_the_archive_identity_and_its_files(self):
        b = _bundle(_file())

        assert b.snapshot_id == "req_1_20260831_120000"
        assert b.url == "https://example.com/p"
        assert b.request_id == "req-1"
        assert b.root == Path("/archives/example_com/req_1")
        assert len(b.files) == 1

    def test_is_frozen(self):
        b = _bundle()

        with pytest.raises(ValidationError):
            b.snapshot_id = "other"

    def test_add_returns_a_new_bundle_and_leaves_the_original_untouched(self):
        original = _bundle(_file("archive.warc"))

        extended = original.add(_file("screenshot.png", media_type="image/png"))

        assert extended is not original
        assert [f.name for f in original.files] == ["archive.warc"]
        assert [f.name for f in extended.files] == ["archive.warc", "screenshot.png"]

    def test_add_preserves_identity_fields(self):
        original = _bundle()

        extended = original.add(_file())

        assert extended.snapshot_id == original.snapshot_id
        assert extended.url == original.url
        assert extended.request_id == original.request_id
        assert extended.root == original.root

    def test_files_cannot_be_mutated_in_place(self):
        """Backends run concurrently, so one must not mutate another's view of the files."""
        b = _bundle(_file())

        with pytest.raises(AttributeError):
            b.files.append(_file("screenshot.png"))

    def test_a_list_of_files_is_stored_as_a_tuple(self):
        """Callers may pass a list; it is still not mutable once it is in the bundle."""
        b = ArchiveBundle(
            snapshot_id="s",
            url="https://example.com",
            request_id="r",
            root=Path("/a"),
            files=[_file()],
        )

        assert isinstance(b.files, tuple)

    def test_wrong_types_are_rejected_on_construction(self):
        with pytest.raises(ValidationError):
            ArchiveBundle(
                snapshot_id="s",
                url="https://example.com",
                request_id="r",
                root=Path("/a"),
                files=["not-a-file"],
            )

    def test_total_size_sums_the_files(self):
        b = _bundle(_file("archive.warc", size=100), _file("screenshot.png", size=250))

        assert b.total_size == 350

    def test_total_size_of_an_empty_bundle_is_zero(self):
        assert _bundle().total_size == 0

    def test_is_unfiltered__logs_are_carried_too(self):
        """The bundle describes what exists; each backend decides what it publishes."""
        b = _bundle(_file("archive.warc"), _file("scoop.log", media_type="text/plain"))

        assert [f.name for f in b.files] == ["archive.warc", "scoop.log"]

    def test_model_dump_is_json_serialisable(self):
        b = _bundle(_file("archive.warc", size=100), _file("screenshot.png", size=250))

        payload = json.loads(json.dumps(b.model_dump(mode="json")))

        assert payload["snapshot_id"] == "req_1_20260831_120000"
        assert payload["root"] == "/archives/example_com/req_1"
        assert payload["total_size"] == 350
        assert [f["name"] for f in payload["files"]] == ["archive.warc", "screenshot.png"]
