"""Check upload file selection and request settings using a fake HTTP client."""

from datetime import datetime
from pathlib import Path

import pytest
from civers_common import ConfigurationError

from domain.artifacts import ArchiveBundle, ArtifactFile
from storage_layer.civers_rest_api_storage_strategy import CiversRestApiStorageStrategy

pytestmark = [pytest.mark.unit]

# A real scoop+singlefile run leaves these nine files behind.
REAL_RUN = {
    "archive.warc": "application/warc",
    "dom-snapshot.html": "text/html",
    "archive_generator_metadata.json": "application/json",
    "scoop_stderr.log": "text/plain",
    "scoop_stdout.log": "text/plain",
    "screenshot.png": "image/png",
    "singlefile.html": "text/html",
    "singlefile_stderr.log": "text/plain",
    "singlefile_stdout.log": "text/plain",
}

# Files accepted by the upload API for this capture.
EXPECTED_UPLOAD_FILES = sorted([
    ("archive.warc", "application/warc"),
    ("archive_generator_metadata.json", "application/json"),
    ("dom-snapshot.html", "text/html"),
    ("screenshot.png", "image/png"),
    ("singlefile.html", "text/html"),
])


def _bundle(names=None, root="/no/such/folder", create=False):
    names = REAL_RUN if names is None else names
    root = Path(root)
    if create:
        root.mkdir(parents=True, exist_ok=True)
        for n in names:
            (root / n).write_bytes(b"xxxxxxxxxx")
    return ArchiveBundle(
        snapshot_id="req_1_20260901_120000",
        url="https://sh.museum-digital.de/object/194",
        request_id="debugg_req_23423",
        root=root,
        files=tuple(
            ArtifactFile(
                name=n,
                path=root / n,
                size=10,
                media_type=mt,
                created=datetime(2026, 9, 1, 12, 0, 0),
            )
            for n, mt in names.items()
        ),
    )


class FakeResponse:
    status_code = 200

    def json(self):
        return {"snapshot_id": "snap-1", "artifacts_uploaded": []}


class RecordingClient:
    """Stands in for httpx, capturing exactly what one upload sent."""

    posts = []
    options = []

    def __init__(self, **kwargs):
        RecordingClient.options.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, data=None, files=None, headers=None):
        RecordingClient.posts.append({
            "url": url,
            "data": data,
            "headers": headers,
            "files": [(name, ctype) for _field, (name, _buf, ctype) in files],
        })
        return FakeResponse()


@pytest.fixture
def strategy(monkeypatch):
    RecordingClient.posts = []
    RecordingClient.options = []
    monkeypatch.setattr(
        "storage_layer.civers_rest_api_storage_strategy.httpx.AsyncClient",
        RecordingClient,
    )
    return CiversRestApiStorageStrategy(upload_url="http://localhost:8000/api/upload")


@pytest.fixture
def files(tmp_path):
    """Build a bundle whose files really exist, so the upload can read them."""
    def build(names=None):
        return _bundle(names, root=str(tmp_path / "archive"), create=True)
    return build


def _uploaded():
    return sorted(RecordingClient.posts[0]["files"])


class TestSelection:
    @pytest.mark.asyncio
    async def test_publishes_exactly_what_it_published_before(self, strategy, files):
        """Select archive files and metadata while excluding capture logs."""
        await strategy.store_artifacts(files())

        assert _uploaded() == EXPECTED_UPLOAD_FILES

    @pytest.mark.asyncio
    async def test_logs_are_not_published(self, strategy, files):
        await strategy.store_artifacts(files())

        assert not [n for n, _ in _uploaded() if n.endswith(".log")]

    @pytest.mark.asyncio
    async def test_the_record_is_published_under_the_name_it_was_written_with(self, strategy, files):
        """No rename on upload: the generator already writes the name the API stores."""
        await strategy.store_artifacts(files())

        names = [n for n, _ in _uploaded()]
        assert "archive_generator_metadata.json" in names
        assert "metadata.json" not in names

    @pytest.mark.asyncio
    async def test_media_type_comes_from_the_bundle(self, strategy, files):
        """Not from a second table maintained inside this file."""
        await strategy.store_artifacts(
            files({"archive.warc": "application/x-decided-upstream"})
        )

        assert _uploaded() == [("archive.warc", "application/x-decided-upstream")]

    @pytest.mark.asyncio
    async def test_a_publishable_file_the_run_did_not_produce_is_simply_absent(self, strategy, files):
        """No wacz this run: it is skipped, not an error."""
        await strategy.store_artifacts(files({"archive.warc": "application/warc"}))

        assert _uploaded() == [("archive.warc", "application/warc")]

    @pytest.mark.asyncio
    async def test_a_bundle_with_nothing_publishable_fails_cleanly(self, strategy, files):
        result = await strategy.store_artifacts(files({"scoop_stdout.log": "text/plain"}))

        assert result.success is False
        assert "No artifact files" in result.error_message
        assert RecordingClient.posts == [], "nothing should be sent"


class TestItDoesNotGoBehindTheBundle:
    def test_selection_needs_no_filesystem(self, strategy):
        """Choose upload files from the bundle without scanning the folder."""
        bundle = _bundle(root="/definitely/not/here")

        chosen = strategy._select(bundle)

        assert not Path("/definitely/not/here").exists()
        assert sorted(f.name for f in chosen) == [n for n, _ in EXPECTED_UPLOAD_FILES]


class TestTheUpload:
    @pytest.mark.asyncio
    async def test_exhausted_upload_returns_original_failure_and_file_names(self, strategy, files, monkeypatch):
        from unittest.mock import AsyncMock
        import httpx

        post = AsyncMock(side_effect=httpx.ConnectError("API unavailable"))
        monkeypatch.setattr(RecordingClient, "post", post)
        result = await strategy.store_artifacts(files({"archive.warc": "application/warc"}))

        assert result.success is False
        assert "API unavailable" in result.error_message
        assert result.metadata["files_attempted"] == ["archive.warc"]
        assert post.await_count == strategy.retry_attempts

    @pytest.mark.asyncio
    async def test_one_request_carries_every_selected_file(self, strategy, files):
        await strategy.store_artifacts(files())

        assert len(RecordingClient.posts) == 1
        assert len(RecordingClient.posts[0]["files"]) == 5

    @pytest.mark.asyncio
    async def test_the_form_still_identifies_the_archive(self, strategy, files):
        await strategy.store_artifacts(files())

        assert RecordingClient.posts[0]["data"] == {
            "url": "https://sh.museum-digital.de/object/194",
            "request_id": "debugg_req_23423",
            "allow_existing": "true",
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("via_config", [False, True])
@pytest.mark.parametrize("value,verify,authenticated", [
    (False, False, False),
    ("false", False, False),
    (" TRUE ", True, True),
    ("off", False, False),
    ("0", False, False),
    (None, True, False),
])
async def test_backend_boolean_settings_reach_upload(strategy, files, via_config, value, verify, authenticated):
    settings = {
        "upload_url": "https://example.com/api/upload",
        "verify_ssl": value,
        "auth": {"enabled": value, "token": "test-token"},
    }
    backend = (
        CiversRestApiStorageStrategy.from_config(settings) if via_config
        else CiversRestApiStorageStrategy(**settings)
    )
    result = await backend.store_artifacts(files())

    assert result.success
    assert RecordingClient.options[0]["verify"] is verify
    expected_headers = {"Authorization": "Bearer test-token"} if authenticated else {}
    assert RecordingClient.posts[0]["headers"] == expected_headers


@pytest.mark.parametrize("value", ["flase", "maybe", 1, []])
@pytest.mark.parametrize("field", ["verify_ssl", "auth.enabled"])
def test_backend_rejects_invalid_switches(field, value):
    settings = {"upload_url": "https://example.com/api/upload"}
    if field == "verify_ssl":
        settings["verify_ssl"] = value
    else:
        settings["auth"] = {"enabled": value}
    with pytest.raises(ConfigurationError, match=field):
        CiversRestApiStorageStrategy.from_config(settings)
