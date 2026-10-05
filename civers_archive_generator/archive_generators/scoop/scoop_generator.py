"""Archive generation via the Scoop (Node.js) CLI."""

import asyncio
import time as time_module
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from ..archive_result import ArtifactResult, ArtifactStatus
from ..base_generator import BaseGenerator

# Check the supported Node runtime and matching Playwright browser before capture.
_RUNTIME_PROBE = """
if (Number(process.versions.node.split(".")[0]) < 22) {
  console.error("Scoop 0.7.0 requires Node 22 or newer; found " + process.version +
    ". Run nvm use, or update SCOOP_NODE_BIN.");
  process.exit(1);
}
const browser = require("playwright").chromium.executablePath();
if (!require("fs").existsSync(browser)) {
  console.error("Playwright chromium is missing at " + browser +
    ". Run: npx playwright install chromium");
  process.exit(1);
}
"""


class ScoopGenerator(BaseGenerator):
    """Capture WARC/WACZ, screenshots, rendered HTML and summaries with Scoop."""

    CAPABILITIES = ["warc", "screenshot", "dom-snapshot", "summary"]

    def __init__(self, config):
        super().__init__(config)
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Check that Scoop loads, Node is supported and Chromium is installed."""
        project_dir = Path(__file__).resolve().parents[2]
        cmd = self.config.app.scoop_cli_command.split()
        node = cmd[0] if cmd and Path(cmd[0]).name in ("node", "node.exe") else "node"

        self._require(cmd + ["--version"], "Scoop CLI", project_dir)
        self._require([node, "-e", _RUNTIME_PROBE], "Node runtime", project_dir / "lib" / "scoop")

    def _require(self, cmd: List[str], what: str, cwd: Path) -> None:
        """Run a dependency check and include its error in a ValueError."""
        try:
            subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30, check=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            detail = (getattr(e, "stderr", "") or "").strip() or e
            self.logger.error(f"❌ Scoop not ready — {what}: {detail}")
            raise ValueError(f"Scoop not ready — {what}: {detail}") from None

    async def _run_scoop(self, url: str, output_folder: str, requested_artifacts: List[str]) -> Dict[str, Any]:
        """Invoke Scoop CLI and save logs to output folder."""

        output_format = "wacz"
        if "warc" in requested_artifacts and "wacz" not in requested_artifacts:
            output_format = "warc"

        output_file = os.path.join(output_folder, f"archive.{output_format}")

        cmd = self.config.app.scoop_cli_command.split()
        cmd += ["-o", output_file, "-f", output_format]

        screenshot_flag = "true" if "screenshot" in requested_artifacts else "false"
        dom_snapshot_flag = "true" if "dom-snapshot" in requested_artifacts else "false"

        cmd += [
            "--screenshot", screenshot_flag,
            "--dom-snapshot", dom_snapshot_flag,
            "--export-attachments-output", output_folder,
            "--provenance-summary", "false",
            "--capture-certificates-as-attachment-timeout", "0",  # seconds
        ]

        if "summary" in requested_artifacts:
            cmd += ["--json-summary-output", os.path.join(output_folder, "summary.json")]

        # Configured arguments can override the defaults above.
        if self.config.app.scoop_extra_args:
            cmd += list(self.config.app.scoop_extra_args)

        cmd += ["--", url]

        self.logger.info(f"🚀 Running Scoop: {' '.join(cmd)}")
        scoop_start_time = time_module.time()

        project_dir = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env['PWD'] = str(project_dir)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        timeout = self.config.app.scoop_timeout_sec
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            exit_code = process.returncode
            timed_out = False
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            stdout, stderr = b"", b"Scoop process timed out"
            exit_code = None
            timed_out = True

        scoop_elapsed = time_module.time() - scoop_start_time
        self.logger.info(f"⏱️ Scoop subprocess completed in {scoop_elapsed:.2f}s (exit_code={exit_code}, timed_out={timed_out})")

        await self._save_log_to_file(stdout, output_folder, "scoop_stdout.log")
        await self._save_log_to_file(stderr, output_folder, "scoop_stderr.log")

        return {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "output_file": output_file,
            "stderr": stderr.decode('utf-8', errors='ignore') if stderr else ""
        }

    def _analyze_artifacts(self, output_folder: str, requested_artifacts: List[str]) -> List[ArtifactResult]:
        """Match requested artifacts to nonempty Scoop output files."""
        artifacts = []
        output_path = Path(output_folder)

        mapping = {
            "warc": ("*.wacz", "archive.wacz", "*.warc", "*.warc.gz"),
            "screenshot": ("screenshot.png", "*.png"),
            "dom-snapshot": ("dom-snapshot.html",),
            "summary": ("summary.json",),
        }

        for artifact_name in requested_artifacts:
            if artifact_name not in mapping:
                continue

            patterns = mapping[artifact_name]
            found_file = None
            for pattern in patterns:
                matches = list(output_path.glob(pattern))
                if matches:
                    found_file = max(matches, key=lambda p: p.stat().st_size)
                    break

            if found_file and found_file.stat().st_size > 0:
                self.logger.info(f"✅ Found artifact: {artifact_name} -> {found_file.name} ({found_file.stat().st_size} bytes)")
                artifacts.append(ArtifactResult(
                    name=artifact_name,
                    status=ArtifactStatus.SUCCESS,
                    file_path=str(found_file),
                    file_size=found_file.stat().st_size
                ))
            else:
                self.logger.warning(f"❌ Missing artifact: {artifact_name}")
                artifacts.append(ArtifactResult(
                    name=artifact_name,
                    status=ArtifactStatus.FAILED,
                    error="Artifact not found"
                ))

        return artifacts


    async def generate_archive(
        self,
        url: str,
        output_folder: str,
        requested_artifacts: List[str]
    ) -> List[ArtifactResult]:
        """Run Scoop once and return the requested artifact results."""
        try:
            run_result = await self._run_scoop(url, output_folder, requested_artifacts)

            artifacts = self._analyze_artifacts(output_folder, requested_artifacts)

            # If Scoop exited with an error, append details to failed artifacts
            exit_code = run_result.get("exit_code")
            if exit_code is not None and exit_code != 0:
                stderr_text = run_result.get("stderr", "").strip()
                error_msg = "Scoop subprocess failed"
                if stderr_text:
                    lines = [line.strip() for line in stderr_text.split("\n") if line.strip()]
                    error_lines = [
                        line for line in lines
                        if "error" in line.lower() or "fail" in line.lower()
                    ]
                    if error_lines:
                        error_msg = f"Scoop error: {error_lines[-1]}"
                    elif lines:
                        error_msg = f"Scoop error: {lines[-1]}"

                for artifact in artifacts:
                    if artifact.status == ArtifactStatus.FAILED:
                        artifact.error = f"Scoop execution failed (exit={exit_code}). Details: {error_msg}"

            return artifacts

        except Exception as e:
            self.logger.error(f"Scoop generation failed: {e}")
            return [
                ArtifactResult(name=name, status=ArtifactStatus.FAILED, error=str(e))
                for name in requested_artifacts
            ]
