#!/usr/bin/env python3
"""One Browsertrix crawl at a time. The worker exclusively owns job cleanup."""

import fcntl
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

JOBS = Path(os.environ.get("BROWSERTRIX_JOBS_DIR", "/jobs"))
POLL_SECONDS = int(os.environ.get("BROWSERTRIX_WORKER_POLL_MS", "1500")) / 1000
TIMEOUT_SECONDS = int(os.environ.get("BROWSERTRIX_WORKER_TIMEOUT_SEC", "300"))
JOB_TTL_SECONDS = int(os.environ.get("BROWSERTRIX_JOB_TTL_SEC", "900"))
STOP_GRACE_SECONDS = 5
stopping = False
logger = logging.getLogger("browsertrix-worker")


def write_result(job, result):
    temporary = job / "result.json.tmp"
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(job / "result.json")


def stop_crawl(child):
    """Stop the job's process group, including its browser and Redis children."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        child.poll()
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()


def clean_redis_state():
    """Stop leftover Redis processes and remove their dump between captures."""
    subprocess.run(["pkill", "-9", "-x", "redis-server"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path("/tmp/dump.rdb").unlink(missing_ok=True)


def run_crawl(job, args):
    if any(arg.split("=", 1)[0] == "--cwd" for arg in args):
        raise ValueError("The worker owns --cwd; update the generator to omit it")
    clean_redis_state()
    with (job / "crawl.log").open("wb") as log:
        child = subprocess.Popen(["crawl", *args, "--cwd", str(job.absolute())], stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + TIMEOUT_SECONDS
        try:
            while child.poll() is None:
                error = None
                if stopping:
                    error = "Worker shutting down"
                elif (job / "cancel").exists():
                    error = "Capture cancelled by caller"
                elif time.monotonic() >= deadline:
                    error = "Crawl execution timeout"
                if error:
                    stop_crawl(child)
                    return {"exit_code": -1, "error": error}
                time.sleep(POLL_SECONDS)
            code = child.returncode
            return {"exit_code": code, "signal": -code if code < 0 else None}
        finally:
            # Also remove any descendants left after the crawl launcher exits.
            stop_crawl(child)


def process_job(job):
    result_file = job / "result.json"
    if result_file.exists():
        if (job / "ack").exists() or time.time() - result_file.stat().st_mtime > JOB_TTL_SECONDS:
            shutil.rmtree(job)
        return
    if (job / "running").exists():
        # A previous worker stopped before writing the result.
        write_result(job, {"exit_code": -1, "error": "Worker interrupted during capture"})
        return
    if (job / "cancel").exists():
        write_result(job, {"exit_code": -1, "error": "Capture cancelled before start"})
        return
    if not (job / "cmd.json").exists():
        if time.time() - job.stat().st_mtime > JOB_TTL_SECONDS:
            shutil.rmtree(job)  # Job expired before its command file was ready.
        return

    (job / "running").touch(exist_ok=False)
    try:
        args = json.loads((job / "cmd.json").read_text(encoding="utf-8"))
        if not isinstance(args, list) or not args or not all(isinstance(arg, str) for arg in args):
            raise ValueError("cmd.json must be a nonempty array of strings")
        logger.info("Starting job %s", job.name)
        result = run_crawl(job, args)
    except Exception as exc:
        logger.exception("Job %s failed", job.name)
        result = {"exit_code": -1, "error": str(exc)}
    # Leave the running marker if publication fails: never silently rerun the job.
    write_result(job, result)


def tick():
    for job in sorted(JOBS.iterdir()):
        if stopping:
            break
        if job.is_symlink() or not job.is_dir():
            continue
        try:
            process_job(job)
        except OSError:
            logger.exception("Could not process job %s", job.name)


def request_stop(_signum, _frame):
    global stopping
    stopping = True


def is_ready():
    """A held worker lock means startup and directory initialization completed."""
    try:
        with (JOBS / ".worker.lock").open("rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except OSError:
        pass
    return False


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if int(os.environ.get("BROWSERTRIX_WORKER_MAX_CONCURRENT", "1")) != 1:
        raise ValueError("This worker supports exactly one crawl at a time")
    if min(POLL_SECONDS, TIMEOUT_SECONDS, JOB_TTL_SECONDS) <= 0:
        raise ValueError("Polling interval, timeout and retention must be positive")
    JOBS.mkdir(parents=True, exist_ok=True)
    JOBS.chmod(0o1777)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, request_stop)
    # Allow one worker per jobs folder; release the lock on exit.
    with (JOBS / ".worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Watching %s; one crawl at a time", JOBS)
        while not stopping:
            try:
                tick()
            except OSError:
                logger.exception("Could not scan jobs directory")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    if sys.argv[1:] == ["--healthcheck"]:
        sys.exit(0 if is_ready() else 1)
    main()
