"""Check Browsertrix job handling and extraction from synthetic WACZ files."""

import asyncio
import fcntl
import io
import json
import os
import signal
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter

from archive_generators.browsertrix.browsertrix_generator import BrowsertrixGenerator
from archive_generators.browsertrix import worker

URL = "https://example.com/page"
FINAL = "https://example.com/final"
PNG = b"\x89PNG\r\n\x1a\nfixture"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    config = SimpleNamespace(app=SimpleNamespace(
        browsertrix_jobs_dir=str(jobs), browsertrix_timeout_sec=2,
        browsertrix_extra_args=["--scopeType", "page", "--pageLimit", "1"],
    ))
    generator = BrowsertrixGenerator(config)
    monkeypatch.setattr(generator, "POLL_SECONDS", 0.005)
    monkeypatch.setattr(worker, "JOBS", jobs)
    monkeypatch.setattr(worker, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(worker, "TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(worker, "STOP_GRACE_SECONDS", 0.1)
    monkeypatch.setattr(worker, "stopping", False)
    # Never touch the host's Redis processes from a test.
    monkeypatch.setattr(worker, "clean_redis_state", lambda: None)
    return generator, jobs, output


def write_wacz(job, *, screenshot=True, redirect=True):
    collection = job / "collections" / "cap"
    collection.mkdir(parents=True)
    stream = io.BytesIO()
    writer = WARCWriter(stream, gzip=True)

    def response(uri, body, status="200 OK", headers=()):
        http = StatusAndHeaders(status, [("Content-Type", "text/html"), *headers], protocol="HTTP/1.1")
        writer.write_record(writer.create_warc_record(
            uri, "response", payload=io.BytesIO(body), http_headers=http,
        ))

    # Final HTML precedes its redirect in archive order to exercise two-pass matching.
    response(FINAL, b"<html>requested page</html>")
    if redirect:
        response(URL, b"redirect", "302 Found", [("Location", "/final")])
    response("https://example.com/iframe", b"<html>wrong iframe" + b"x" * 5000 + b"</html>")
    for uri, payload in [("urn:fullPage:https://example.com/iframe", PNG * 20)] + (
        # Browsertrix labels the screenshot with the original crawl URL.
        [("urn:fullPage:" + URL, PNG)] if screenshot else []
    ):
        writer.write_record(writer.create_warc_record(
            uri, "resource", payload=io.BytesIO(payload),
            warc_headers_dict={"Content-Type": "image/png"},
        ))
    with zipfile.ZipFile(collection / "cap.wacz", "w") as archive:
        archive.writestr("datapackage.json", json.dumps({"profile": "data-package", "resources": []}))
        archive.writestr("archive/data.warc.gz", stream.getvalue())
        archive.writestr("pages/pages.jsonl", json.dumps({"url": URL, "title": "Page", "status": 200}))


async def wait_for_job(jobs):
    async with asyncio.timeout(2):
        while not list(jobs.glob("*/cmd.json")):
            await asyncio.sleep(0.001)
    return next(jobs.glob("*/cmd.json")).parent


def test_success_copies_correct_page_then_worker_removes_acknowledged_job(setup):
    generator, jobs, output = setup

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, generator.CAPABILITIES))
        job = await wait_for_job(jobs)
        write_wacz(job)
        worker.write_result(job, {"exit_code": 0})
        results = await task
        assert all(result.is_success for result in results)
        assert (output / "dom-snapshot.html").read_bytes() == b"<html>requested page</html>"
        assert (output / "screenshot.png").read_bytes() == PNG
        assert results[0].metadata["format"] == "wacz"
        assert results[2].metadata["representation"] == "response-html"
        assert (job / "ack").exists() and (job / "result.json").exists()
        worker.tick()
        assert not job.exists()
        assert (output / "archive.wacz").exists()
    asyncio.run(scenario())


def test_timeout_requests_cancellation_without_deleting_job(setup):
    generator, jobs, output = setup
    generator.config.app.browsertrix_timeout_sec = 0.02
    results = asyncio.run(generator.generate_archive(URL, output, ["warc"]))
    job = next(jobs.iterdir())
    assert not results[0].is_success
    assert (job / "cancel").exists() and (job / "cmd.json").exists()
    worker.tick()
    assert json.loads((job / "result.json").read_text())["exit_code"] == -1


def test_task_cancellation_propagates_and_marks_job(setup):
    generator, jobs, output = setup

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, ["warc"]))
        job = await wait_for_job(jobs)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (job / "cancel").exists() and job.is_dir()
    asyncio.run(scenario())


def test_cancellation_waits_for_extraction_and_does_not_ack_early(setup, monkeypatch):
    generator, jobs, output = setup
    started, release = threading.Event(), threading.Event()

    def collect(*_):
        started.set()
        assert release.wait(2)
        raise ValueError("extraction failure during cancellation")

    monkeypatch.setattr(generator, "_collect_artifacts", collect)

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, ["warc"]))
        job = await wait_for_job(jobs)
        worker.write_result(job, {"exit_code": 0})
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and not (job / "ack").exists()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (job / "cancel").exists()
    asyncio.run(scenario())


def test_missing_screenshot_does_not_fail_archive_or_choose_iframe(setup):
    generator, jobs, output = setup
    job = jobs / "sample"
    write_wacz(job, screenshot=False)
    results = generator._collect_artifacts(job, output, URL, generator.CAPABILITIES)
    assert [result.is_success for result in results] == [True, False, True]
    assert not (output / "screenshot.png").exists()


def test_redirect_keeps_original_screenshot_identity_and_final_html(setup):
    generator, jobs, output = setup
    job = jobs / "redirect"
    write_wacz(job)

    results = generator._collect_artifacts(job, output, URL, generator.CAPABILITIES)

    assert all(result.is_success for result in results)
    assert (output / "screenshot.png").read_bytes() == PNG
    assert (output / "dom-snapshot.html").read_bytes() == b"<html>requested page</html>"
    assert all(result.metadata["captured_url"] == FINAL for result in results)


@pytest.mark.parametrize("requested_url,recorded_url", [
    ("https://example.com", "https://example.com/"),
    ("HTTPS://EXAMPLE.COM:443#section", "https://example.com/"),
])
def test_browser_normalized_root_url_matches_all_artifacts(setup, monkeypatch, requested_url, recorded_url):
    generator, jobs, output = setup
    # Reuse the fixture with both response and screenshot at the browser's URL.
    monkeypatch.setitem(globals(), "URL", recorded_url)
    monkeypatch.setitem(globals(), "FINAL", recorded_url)
    job = jobs / "normalized"
    write_wacz(job, redirect=False)

    results = generator._collect_artifacts(job, output, requested_url, generator.CAPABILITIES)

    assert all(result.is_success for result in results)
    assert results[0].metadata["requested_url"] == requested_url
    assert results[0].metadata["page_title"] == "Page"
    assert (output / "screenshot.png").read_bytes() == PNG


@pytest.mark.parametrize("requested_url,recorded_url", [
    ("https://example.com/article", "https://example.com/article/"),
    ("https://example.com/?id=1", "https://example.com/?id=2"),
    ("https://example.com/Article", "https://example.com/article"),
])
def test_extraction_does_not_match_different_paths_or_queries(setup, monkeypatch, requested_url, recorded_url):
    generator, jobs, output = setup
    monkeypatch.setitem(globals(), "URL", recorded_url)
    monkeypatch.setitem(globals(), "FINAL", recorded_url)
    job = jobs / "different-page"
    write_wacz(job, redirect=False)

    results = generator._collect_artifacts(job, output, requested_url, generator.CAPABILITIES)

    assert [result.is_success for result in results] == [True, False, False]
    assert not (output / "screenshot.png").exists()
    assert not (output / "dom-snapshot.html").exists()


def test_invalid_wacz_fails_even_for_archive_only(setup):
    generator, jobs, output = setup

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, ["warc"]))
        job = await wait_for_job(jobs)
        destination = job / "collections" / "cap" / "cap.wacz"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"not a zip")
        worker.write_result(job, {"exit_code": 0})
        assert not (await task)[0].is_success
    asyncio.run(scenario())


def test_disk_limit_failure_reports_cause_and_preserves_crawl_log(setup):
    generator, jobs, output = setup

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, generator.CAPABILITIES))
        job = await wait_for_job(jobs)
        log = "\n".join(json.dumps(entry) for entry in [
            {"logLevel": "info", "message": "Disk utilization threshold reached 94% > 90%, stopping"},
            {"logLevel": "fatal", "message": "No WARC Files, assuming crawl failed. Quitting"},
        ])
        (job / "crawl.log").write_text(log)
        worker.write_result(job, {"exit_code": 17, "signal": None})
        results = await task
        assert all(not result.is_success for result in results)
        assert all("94% > 90%" in result.error and "Free disk space" in result.error for result in results)
        assert (output / "browsertrix_crawl.log").read_text() == log
        assert (job / "cancel").exists()
        assert not (output / "archive.wacz").exists()

    asyncio.run(scenario())


@pytest.mark.parametrize("log,expected", [
    (None, "See browsertrix_crawl.log"),
    ('not json\n[]\n{"message": 123}\n', "See browsertrix_crawl.log"),
    ('{"logLevel": "fatal", "message": "Browser launch failed"}', "Browser launch failed"),
])
def test_crawl_failure_message_handles_missing_malformed_and_fatal_logs(setup, log, expected):
    generator, jobs, _ = setup
    if log is not None:
        (jobs / "crawl.log").write_text(log)
    message = generator._failure_message(jobs, {"exit_code": 17})
    assert "exit code 17" in message
    assert expected in message


@pytest.mark.parametrize("bad", [["--url", 123], {}, []])
def test_malformed_jobs_do_not_crash_worker(setup, bad):
    _, jobs, _ = setup
    job = jobs / "bad"
    job.mkdir()
    (job / "cmd.json").write_text(json.dumps(bad))
    worker.tick()
    assert json.loads((job / "result.json").read_text())["exit_code"] == -1


def test_interrupted_job_is_failed_instead_of_rerun(setup, monkeypatch):
    _, jobs, _ = setup
    job = jobs / "interrupted"
    job.mkdir()
    (job / "running").touch()
    (job / "cmd.json").write_text('["--url", "https://example.com"]')
    monkeypatch.setattr(worker, "run_crawl", lambda *_: pytest.fail("must not rerun"))
    worker.tick()
    result = json.loads((job / "result.json").read_text())
    assert result["exit_code"] == -1 and "interrupted" in result["error"]


def test_result_write_failure_is_isolated_to_one_job(setup, monkeypatch):
    _, jobs, _ = setup
    for name in ["a-bad", "b-good"]:
        job = jobs / name
        job.mkdir()
        (job / "cancel").touch()
    original = worker.write_result

    def write(job, result):
        if job.name == "a-bad":
            raise PermissionError("simulated disk failure")
        original(job, result)

    monkeypatch.setattr(worker, "write_result", write)
    worker.tick()
    assert (jobs / "b-good" / "result.json").exists()


@pytest.mark.parametrize("reason", ["timeout", "cancel", "shutdown"])
def test_worker_stops_real_subprocess(setup, monkeypatch, reason):
    _, jobs, _ = setup
    job = jobs / "slow"
    job.mkdir()
    real_popen = subprocess.Popen
    children = []

    def start(_args, **kwargs):
        child = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        if reason == "cancel":
            (job / "cancel").touch()
        elif reason == "shutdown":
            monkeypatch.setattr(worker, "stopping", True)
        return child

    monkeypatch.setattr(worker.subprocess, "Popen", start)
    monkeypatch.setattr(worker, "TIMEOUT_SECONDS", 0.02)
    try:
        result = worker.run_crawl(job, ["--url", URL])
        assert result["exit_code"] == -1
        assert children[0].poll() is not None
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def test_retention_removes_unacknowledged_results(setup, monkeypatch):
    _, jobs, _ = setup
    job = jobs / "old"
    job.mkdir()
    worker.write_result(job, {"exit_code": 0})
    os.utime(job / "result.json", (1, 1))
    worker.tick()
    assert not job.exists()


def test_missing_mount_and_empty_request_do_not_create_jobs(setup):
    generator, jobs, output = setup
    assert asyncio.run(generator.generate_archive(URL, output, [])) == []
    jobs.rmdir()
    results = asyncio.run(generator.generate_archive(URL, output, ["warc"]))
    assert not results[0].is_success and not jobs.exists()
    assert "Start the " in results[0].error


@pytest.mark.parametrize("mode", ["host", "docker"])
def test_different_generator_and_worker_paths_share_a_capture(setup, tmp_path, monkeypatch, mode):
    generator, jobs, output = setup
    backing = tmp_path / "host workspace (dev)"
    jobs.rename(backing)
    worker_view = tmp_path / "worker_mount"
    worker_view.symlink_to(backing, target_is_directory=True)
    generator_view = backing
    if mode == "docker":
        generator_view = tmp_path / "generator_mount"
        generator_view.symlink_to(backing, target_is_directory=True)
    generator.config.app.browsertrix_jobs_dir = str(generator_view)
    monkeypatch.setattr(worker, "JOBS", worker_view)
    monkeypatch.setattr(worker, "stop_crawl", lambda _: None)
    commands = []

    def start(command, **_kwargs):
        commands.append(command)
        crawl_dir = Path(command[command.index("--cwd") + 1])
        assert crawl_dir.parent == worker_view
        assert str(generator_view) not in command
        write_wacz(crawl_dir)
        return SimpleNamespace(returncode=0, poll=lambda: 0)

    monkeypatch.setattr(worker.subprocess, "Popen", start)

    async def scenario():
        task = asyncio.create_task(generator.generate_archive(URL, output, generator.CAPABILITIES))
        job = await wait_for_job(generator_view)
        submitted = json.loads((job / "cmd.json").read_text())
        assert "--cwd" not in submitted
        worker.tick()
        results = await task
        assert all(result.is_success for result in results)
        assert len(commands) == 1
        worker.tick()
        assert not job.exists()

    asyncio.run(scenario())


def test_healthcheck_requires_a_live_lock_not_just_a_file(setup):
    _, jobs, _ = setup
    assert not worker.is_ready()
    with (jobs / ".worker.lock").open("a") as lock:
        assert not worker.is_ready()
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert worker.is_ready()
        fcntl.flock(lock, fcntl.LOCK_UN)
    assert not worker.is_ready()


@pytest.mark.parametrize("old_cwd", [["--cwd", "/host/jobs/old"], ["--cwd=/host/jobs/old"]])
def test_worker_rejects_legacy_host_paths_before_starting_crawl(setup, monkeypatch, old_cwd):
    _, jobs, _ = setup
    monkeypatch.setattr(worker, "clean_redis_state", lambda: pytest.fail("must reject before execution"))
    with pytest.raises(ValueError, match="worker owns --cwd"):
        worker.run_crawl(jobs / "old", ["--url", URL, *old_cwd])
