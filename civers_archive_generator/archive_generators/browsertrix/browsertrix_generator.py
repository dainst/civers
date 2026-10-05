"""Submit Browsertrix jobs and collect their artifacts from the shared volume."""

import asyncio
import json
import shutil
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urljoin

from warcio.archiveiterator import ArchiveIterator

from ..archive_result import ArtifactResult, ArtifactStatus
from ..base_generator import BaseGenerator
from .urls import normalize_http_url


class BrowsertrixGenerator(BaseGenerator):

    CAPABILITIES = ["warc", "screenshot", "dom-snapshot"]
    POLL_SECONDS = 1

    async def generate_archive(self, url, output_folder, requested_artifacts):
        """Return one result per requested artifact; propagate task cancellation."""
        if not requested_artifacts:
            return []
        job = None
        try:
            unsupported = set(requested_artifacts) - set(self.CAPABILITIES)
            if unsupported:
                raise ValueError(f"Unsupported artifacts: {sorted(unsupported)}")
            output = Path(output_folder)
            if not output.is_dir():
                raise ValueError(f"Output directory does not exist: {output}")
            jobs = Path(self.config.app.browsertrix_jobs_dir).expanduser().absolute()
            if not jobs.is_dir():
                raise RuntimeError(
                    f"Browsertrix jobs directory is missing: {jobs}. Start the Browsertrix worker "
                    "first and check BROWSERTRIX_JOBS_DIR and its bind mount."
                )
            candidate = jobs / uuid.uuid4().hex
            try:
                candidate.mkdir()
            except PermissionError as exc:
                raise RuntimeError(
                    f"Browsertrix jobs directory is not writable: {jobs}. Wait for "
                    "the Browsertrix worker to become healthy; it initializes permissions."
                ) from exc
            job = candidate
            args = self._crawl_args(url, job, requested_artifacts)
            temporary = job / "cmd.json.tmp"
            temporary.write_text(json.dumps(args), encoding="utf-8")
            # Rename the completed argument file so the worker cannot read partial JSON.
            temporary.replace(job / "cmd.json")

            async with asyncio.timeout(self.config.app.browsertrix_timeout_sec):
                result = await self._wait_for_result(job)
            await self._copy_log(job, output)
            if result.get("exit_code") != 0:
                raise RuntimeError(await asyncio.to_thread(self._failure_message, job, result))

            # Finish filesystem work before allowing the worker to delete its inputs.
            collection = asyncio.create_task(asyncio.to_thread(
                self._collect_artifacts, job, output, url, requested_artifacts
            ))
            try:
                artifacts = await asyncio.shield(collection)
            except asyncio.CancelledError:
                try:
                    await collection
                except Exception:
                    pass
                raise
            self._mark(job, "ack")
            return artifacts
        except asyncio.CancelledError:
            self._mark(job, "cancel")
            raise
        except Exception as exc:
            self._mark(job, "cancel")
            error = str(exc) or "Timed out waiting for Browsertrix (including queue time)"
            self.logger.warning("Browsertrix capture failed: %s", error)
            return [ArtifactResult(name=name, status=ArtifactStatus.FAILED, error=error)
                    for name in requested_artifacts]

    def _crawl_args(self, url, job, requested):
        extra = self.config.app.browsertrix_extra_args or []
        reserved = {"--url", "--seeds", "--cwd", "--collection", "-c", "--crawlid", "--id"}
        if not isinstance(extra, (list, tuple)) or any(not isinstance(arg, str) for arg in extra):
            raise ValueError("browsertrix_extra_args must contain strings")
        if any(arg.split("=", 1)[0].lower() in reserved for arg in extra):
            raise ValueError("Extra arguments cannot override the URL, output path or job ID")
        # The worker supplies --cwd in its own filesystem. Never send a host path.
        args = ["--url", url, "--collection", "cap",
                "--crawlId", job.name, "--generateWACZ"]
        if "screenshot" in requested:
            args += ["--screenshot", "fullPage"]
        # --text to-pages extracts text, not a DOM snapshot, so it is unnecessary.
        return args + list(extra)

    async def _wait_for_result(self, job):
        while True:
            try:
                result = json.loads((job / "result.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                await asyncio.sleep(self.POLL_SECONDS)
                continue
            if not isinstance(result, dict) or type(result.get("exit_code")) is not int:
                raise ValueError("Invalid Browsertrix result.json")
            return result

    @staticmethod
    def _failure_message(job, result):
        """Explain a resource limit when the crawl ends without archive files."""
        messages = []
        try:
            with (job / "crawl.log").open("rb") as log:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 65536))
                tail = log.read().decode("utf-8", errors="replace")
            for line in tail.splitlines():
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or not isinstance(entry.get("message"), str):
                    continue
                message = entry["message"]
                if message.startswith("Disk utilization threshold reached"):
                    return (
                        f"Browsertrix stopped: {message}. Free disk space on the Browsertrix "
                        "worker's filesystem or move it to a larger disk, then retry."
                    )
                if entry.get("logLevel") == "fatal":
                    messages.append(message[:1000])
        except OSError:
            pass
        reason = result.get("error") or (messages[-1] if messages else "See browsertrix_crawl.log")
        return f"Browsertrix crawl failed (exit code {result['exit_code']}): {reason}"

    def _mark(self, job, name):
        if job is not None:
            try:
                (job / name).touch()
            except OSError:
                self.logger.warning("Could not mark Browsertrix job %s as %s", job.name, name)

    async def _copy_log(self, job, output):
        try:
            await asyncio.to_thread(shutil.copyfile, job / "crawl.log",
                                    output / "browsertrix_crawl.log")
        except OSError:
            pass  # Logging must not determine capture success.

    @staticmethod
    def _records(archive):
        for name in archive.namelist():
            if name.startswith("archive/") and name.endswith((".warc", ".warc.gz")):
                with archive.open(name) as stream:
                    yield from ArchiveIterator(stream)

    def _collect_artifacts(self, job, output, url, requested):
        wacz = job / "collections" / "cap" / "cap.wacz"
        with zipfile.ZipFile(wacz) as archive:
            manifest = json.loads(archive.read("datapackage.json"))
            if not isinstance(manifest, dict) or not any(
                n.startswith("archive/") and n.endswith((".warc", ".warc.gz"))
                for n in archive.namelist()
            ) or archive.testzip() is not None:
                raise ValueError("Invalid or damaged WACZ package")

            # Follow HTTP redirects to find the requested page response.
            redirects = {}
            for record in self._records(archive):
                if record.rec_type == "response" and record.http_headers:
                    location = record.http_headers.get_header("Location")
                    if location and record.http_headers.get_statuscode() in {
                        "301", "302", "303", "307", "308"
                    }:
                        source = record.rec_headers.get_header("WARC-Target-URI")
                        if source:
                            try:
                                redirects[normalize_http_url(source)] = normalize_http_url(urljoin(source, location))
                            except ValueError:
                                continue  # Unrelated non-HTTP records cannot identify this page.
            seed = normalize_http_url(url)
            target = seed
            seen = set()
            while target in redirects and target not in seen:
                seen.add(target)
                target = redirects[target]

            metadata = {"requested_url": url, "captured_url": target}
            try:
                for line in archive.read("pages/pages.jsonl").decode("utf-8").splitlines():
                    page = json.loads(line)
                    if not page.get("url"):
                        continue  # The first JSONL entry may describe the page list.
                    if normalize_http_url(page["url"]) in {seed, target}:
                        metadata.update(page_title=page.get("title"), page_status=page.get("status"))
                        break
            except (KeyError, ValueError, AttributeError, TypeError):
                pass

            results = []
            for name in requested:
                details = dict(metadata)
                try:
                    if name == "warc":
                        path = output / "archive.wacz"
                        shutil.copyfile(wacz, path)
                        details["format"] = "wacz"
                    else:
                        # Screenshots use the starting URL; response HTML uses the final redirect URL.
                        artifact_url = seed if name == "screenshot" else target
                        path = self._extract_page_artifact(archive, output, artifact_url, name)
                        details["representation"] = (
                            "response-html" if name == "dom-snapshot" else "full-page-screenshot"
                        )
                    if not path or path.stat().st_size == 0:
                        raise ValueError(f"No {name} found for {target}")
                    results.append(ArtifactResult(
                        name=name, status=ArtifactStatus.SUCCESS, file_path=str(path),
                        file_size=path.stat().st_size, metadata=details,
                    ))
                except Exception as exc:
                    results.append(ArtifactResult(
                        name=name, status=ArtifactStatus.FAILED, error=str(exc), metadata=details,
                    ))
            return results

    def _extract_page_artifact(self, archive, output, target, name):
        for record in self._records(archive):
            uri = record.rec_headers.get_header("WARC-Target-URI") or ""
            if name == "screenshot":
                if record.rec_type != "resource" or not uri.startswith("urn:fullPage:"):
                    continue
                try:
                    matches = normalize_http_url(uri.removeprefix("urn:fullPage:")) == target
                except ValueError:
                    continue
                if not matches:
                    continue
                mime = (record.rec_headers.get_header("Content-Type") or "").lower()
                suffix = ".png" if "image/png" in mime else ".jpg" if "image/jpeg" in mime else None
                if not suffix:
                    continue
                path = output / ("screenshot" + suffix)
            else:
                if record.rec_type != "response":
                    continue
                try:
                    matches = normalize_http_url(uri) == target
                except ValueError:
                    continue
                if not matches:
                    continue
                headers = record.http_headers
                if not headers or "text/html" not in (headers.get_header("Content-Type") or "").lower():
                    continue
                path = output / "dom-snapshot.html"
            with path.open("wb") as dest:
                shutil.copyfileobj(record.content_stream(), dest)
            return path
        return None
