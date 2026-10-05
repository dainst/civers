"""Check capture folder names, creation and file inventory."""
import asyncio
import re
from pathlib import Path

import pytest

from archive_services.archive_workspace import _PACKAGE_ROOT, ArchiveWorkspace


@pytest.fixture
def config(sample_config, tmp_path):
    """Use a real configuration with a temporary archive folder."""
    sample_config.app.archive_directory = str(tmp_path / "archives")
    return sample_config


async def _open(config, url, request_id="req-1"):
    return await ArchiveWorkspace.open(config, url, request_id)


def _folder(url, archive_directory="/archives", request_id="req-1"):
    """The path this URL would get, decided but not created."""
    return ArchiveWorkspace._folder_for(
        archive_directory, url, ArchiveWorkspace._new_snapshot_id(request_id)
    )


@pytest.mark.unit
class TestFolderName:
    """Keep the existing archive folder layout."""

    @pytest.mark.parametrize(
        "url, expected_domain, expected_page",
        [
            # The real archive that confirmed the convention.
            ("https://sh.museum-digital.de/object/194", "sh_museum_digital_de", "object_194"),
            # No path at all -> home_page
            ("https://example.com", "example_com", "home_page"),
            # Trailing slash only -> still home_page
            ("https://example.com/", "example_com", "home_page"),
            # Dots and hyphens in the host both become underscores
            ("https://my-site.co.uk/a", "my_site_co_uk", "a"),
            # Nested path segments join with underscores; hyphens too
            ("https://example.com/a/b-c/d", "example_com", "a_b_c_d"),
            # Port is not part of the folder name
            ("https://example.com:8080/p", "example_com", "p"),
            # Host dots become underscores; page extensions keep their dots.
            ("https://sub.domain.example.com/x-y/z.html", "sub_domain_example_com", "x_y_z.html"),
            ("https://example.com/file.tar.gz", "example_com", "file.tar.gz"),
            ("https://example.com/a.b/c.d", "example_com", "a.b_c.d"),
        ],
    )
    def test_domain_and_page_segments(self, url, expected_domain, expected_page):
        path = _folder(url)

        assert path.parent.parent.name == expected_domain
        assert path.parent.name == expected_page

    def test_full_layout_for_the_known_archive(self):
        path = _folder("https://sh.museum-digital.de/object/194", request_id="debugg_req_23423")

        relative = path.relative_to("/archives")
        assert relative.parts[:2] == ("sh_museum_digital_de", "object_194")
        assert re.fullmatch(r"req_debugg_req_23423_\d{8}_\d{6}", relative.parts[2])

    def test_deciding_a_folder_does_not_create_it(self, tmp_path):
        path = _folder("https://example.com/p", archive_directory=str(tmp_path))

        assert not path.exists()
        assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
class TestSnapshotId:
    @pytest.mark.parametrize(
        "request_id, expected",
        [
            ("debugg_req_23423", "debugg_req_23423"),   # already safe
            ("req/with slashes", "reqwithslashes"),     # dropped, not replaced
            ("a.b@c!d", "abcd"),                        # punctuation dropped
            ("keep-me_1", "keep-me_1"),                 # hyphen and underscore survive
        ],
    )
    def test_request_id_is_stripped_to_safe_characters(self, request_id, expected):
        assert ArchiveWorkspace._new_snapshot_id(request_id).startswith(f"req_{expected}_")

    def test_carries_a_timestamp(self):
        assert re.fullmatch(r"req_r1_\d{8}_\d{6}", ArchiveWorkspace._new_snapshot_id("r1"))

    def test_is_the_final_path_segment(self):
        snapshot_id = ArchiveWorkspace._new_snapshot_id("r1")

        path = ArchiveWorkspace._folder_for("/archives", "https://example.com/p", snapshot_id)

        assert path.name == snapshot_id


@pytest.mark.unit
class TestArchiveDirectoryRoot:
    def test_absolute_archive_directory_is_used_as_is(self):
        path = _folder("https://example.com/p", archive_directory="/somewhere/else")

        assert path.is_relative_to(Path("/somewhere/else"))

    def test_relative_archive_directory_resolves_against_the_package_root(self):
        path = _folder("https://example.com/p", archive_directory="archives")

        assert path.is_relative_to(_PACKAGE_ROOT / "archives")

    def test_nested_relative_directory_also_resolves(self):
        path = _folder("https://example.com/p", archive_directory="nested/rel/dir")

        assert path.is_relative_to(_PACKAGE_ROOT / "nested/rel/dir")

    def test_package_root_is_the_service_package_not_the_module_folder(self):
        assert (_PACKAGE_ROOT / "archive_services").is_dir()
        assert _PACKAGE_ROOT.name == "civers_archive_generator"


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpen:
    async def test_directory_exists_afterwards(self, config):
        ws = await _open(config, "https://example.com/p")

        assert ws.path.is_dir()

    async def test_carries_the_identity_of_what_it_holds(self, config):
        ws = await _open(config, "https://example.com/p", "req-42")

        assert ws.url == "https://example.com/p"
        assert ws.request_id == "req-42"
        assert ws.snapshot_id == ws.path.name
        assert ws.snapshot_id.startswith("req_req-42_")

    async def test_opening_twice_is_safe(self, config):
        first = await _open(config, "https://example.com/p")
        again = await _open(config, "https://example.com/p")

        assert first.path.is_dir()
        assert again.path.is_dir()

    async def test_the_directory_creation_does_not_block_the_event_loop(self, config, monkeypatch):
        """mkdir is filesystem I/O, so it must be handed to a thread, per the async rule."""
        calls = []
        real_to_thread = asyncio.to_thread

        async def spy(fn, *args, **kwargs):
            calls.append(fn)
            return await real_to_thread(fn, *args, **kwargs)

        monkeypatch.setattr("archive_services.archive_workspace.asyncio.to_thread", spy)

        ws = await _open(config, "https://example.com/p")

        assert calls, "expected directory creation to be dispatched via asyncio.to_thread"
        assert ws.path.is_dir()


# Sample files from a Scoop and SingleFile capture.
REAL_ARCHIVE_FILES = [
    "archive.warc",
    "dom-snapshot.html",
    "archive_generator_metadata.json",
    "scoop_stderr.log",
    "scoop_stdout.log",
    "screenshot.png",
    "singlefile.html",
    "singlefile_stderr.log",
    "singlefile_stdout.log",
]


@pytest.fixture
async def stocked(config):
    """A workspace holding the same nine files a real archive run produces."""
    ws = await _open(config, "https://sh.museum-digital.de/object/194", "debugg_req_23423")
    for i, name in enumerate(REAL_ARCHIVE_FILES):
        (ws.path / name).write_bytes(b"x" * (i + 1))
    return ws


@pytest.mark.unit
@pytest.mark.asyncio
class TestInventory:
    async def test_lists_every_file_including_the_logs(self, stocked):
        """The bundle says what exists; choosing what to publish is a backend's job."""
        bundle = await stocked.inventory()

        assert sorted(f.name for f in bundle.files) == sorted(REAL_ARCHIVE_FILES)
        assert len([f for f in bundle.files if f.name.endswith(".log")]) == 4

    async def test_carries_the_archive_identity(self, stocked):
        bundle = await stocked.inventory()

        assert bundle.snapshot_id == stocked.snapshot_id
        assert bundle.url == "https://sh.museum-digital.de/object/194"
        assert bundle.request_id == "debugg_req_23423"
        assert bundle.root == stocked.path

    async def test_sizes_come_from_the_filesystem(self, stocked):
        bundle = await stocked.inventory()

        by_name = {f.name: f for f in bundle.files}
        for i, name in enumerate(REAL_ARCHIVE_FILES):
            assert by_name[name].size == i + 1
        assert bundle.total_size == sum(range(1, len(REAL_ARCHIVE_FILES) + 1))

    async def test_each_file_is_stat_ed_exactly_once(self, stocked, monkeypatch):
        """Read each file record once while building the inventory."""
        from pathlib import Path as _P

        calls = []
        real_stat = _P.stat

        def counting_stat(self, *a, **kw):
            calls.append(self.name)
            return real_stat(self, *a, **kw)

        monkeypatch.setattr(_P, "stat", counting_stat)

        await stocked.inventory()

        stat_counts = {name: calls.count(name) for name in REAL_ARCHIVE_FILES}
        assert set(stat_counts.values()) == {1}, stat_counts

    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("archive.warc", "application/warc"),
            ("archive.wacz", "application/octet-stream"),
            ("singlefile.html", "text/html"),
            ("dom-snapshot.html", "text/html"),
            ("screenshot.png", "image/png"),
            ("archive_generator_metadata.json", "application/json"),
            ("scoop_stdout.log", "text/plain"),
            ("mystery.bin", "application/octet-stream"),
            ("no_extension", "application/octet-stream"),
        ],
    )
    async def test_media_type_per_extension(self, config, filename, expected):
        ws = await _open(config, "https://example.com/p")
        (ws.path / filename).write_bytes(b"x")

        bundle = await ws.inventory()

        assert bundle.files[0].media_type == expected

    async def test_does_not_descend_into_subdirectories(self, stocked):
        """Matches today's iterdir(); recursing would change what gets uploaded."""
        nested = stocked.path / "subdir"
        nested.mkdir()
        (nested / "buried.warc").write_bytes(b"x")

        bundle = await stocked.inventory()

        assert "buried.warc" not in [f.name for f in bundle.files]
        assert "subdir" not in [f.name for f in bundle.files]
        assert len(bundle.files) == len(REAL_ARCHIVE_FILES)

    async def test_empty_directory_gives_an_empty_bundle(self, config):
        ws = await _open(config, "https://example.com/p")

        bundle = await ws.inventory()

        assert bundle.files == ()
        assert bundle.total_size == 0

    async def test_missing_directory_raises(self, config):
        ws = await _open(config, "https://example.com/p")
        ws.path.rmdir()

        with pytest.raises(FileNotFoundError):
            await ws.inventory()

    async def test_walk_does_not_block_the_event_loop(self, stocked, monkeypatch):
        calls = []
        real_to_thread = asyncio.to_thread

        async def spy(fn, *args, **kwargs):
            calls.append(fn)
            return await real_to_thread(fn, *args, **kwargs)

        monkeypatch.setattr("archive_services.archive_workspace.asyncio.to_thread", spy)

        await stocked.inventory()

        assert calls, "expected the directory walk to be dispatched via asyncio.to_thread"


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatOne:
    async def test_describes_a_single_named_file(self, stocked):
        f = await stocked.stat_one("archive_generator_metadata.json")

        assert f.name == "archive_generator_metadata.json"
        assert f.path == stocked.path / "archive_generator_metadata.json"
        assert f.media_type == "application/json"
        assert f.size == REAL_ARCHIVE_FILES.index("archive_generator_metadata.json") + 1

    async def test_result_can_be_added_to_a_bundle(self, stocked):
        """This is how the record joins the set after the service writes it."""
        bundle = await stocked.inventory()

        extended = bundle.add(await stocked.stat_one("archive_generator_metadata.json"))

        assert len(extended.files) == len(bundle.files) + 1

    async def test_missing_file_raises(self, stocked):
        with pytest.raises(FileNotFoundError):
            await stocked.stat_one("not_there.warc")

    async def test_does_not_block_the_event_loop(self, stocked, monkeypatch):
        calls = []
        real_to_thread = asyncio.to_thread

        async def spy(fn, *args, **kwargs):
            calls.append(fn)
            return await real_to_thread(fn, *args, **kwargs)

        monkeypatch.setattr("archive_services.archive_workspace.asyncio.to_thread", spy)

        await stocked.stat_one("archive.warc")

        assert calls, "expected the stat to be dispatched via asyncio.to_thread"
