"""Archive generation via the SingleFile CLI."""

import asyncio
import time as time_module
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any

import aiofiles

from ..archive_result import ArtifactResult, ArtifactStatus
from ..base_generator import BaseGenerator

class SingleFileGenerator(BaseGenerator):
    """Save one self-contained HTML file with the SingleFile CLI."""
    CURRENT_DIRECTORY = Path(__file__).parent.resolve()
    CAPABILITIES = ["singlefile"]

    def __init__(self, config):
        super().__init__(config)
        self._chromium_path = None
        binary = Path(self.config.app.singlefile_binary_path).expanduser()
        if not binary.is_absolute():
            binary = self.CURRENT_DIRECTORY.parents[1] / binary
        self.binary_path = str(binary.resolve())
        self._validate_dependencies()

    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        self.logger.info("🔍 Validating SingleFile dependencies...")
        try:
            if not Path(self.binary_path).exists() or not os.access(self.binary_path, os.X_OK):
                raise RuntimeError(f"SingleFile binary not found or not executable: {self.binary_path}")
            
            subprocess.run([self.binary_path, "--version"], capture_output=True, text=True, timeout=10, check=True)
            
            self._chromium_path = self._get_playwright_chromium_path_sync()
            if not Path(self._chromium_path).exists():
                raise RuntimeError(f"Chromium browser not found at {self._chromium_path}")
        except Exception as e:
            self.logger.error(f"❌ SingleFile dependency validation failed: {e}")
            raise ValueError(f"SingleFile dependencies not available: {e}")

    def _get_playwright_chromium_path_sync(self) -> str:
        """Get the Chromium browser executable path."""
        env_path = os.environ.get('CHROMIUM_PATH')
        if env_path and Path(env_path).exists():
            return env_path
            
        home = Path.home()
        playwright_cache = home / ".cache" / "ms-playwright"
        if playwright_cache.exists():
            chromium_dirs = sorted(playwright_cache.glob("chromium-*"), reverse=True)
            for chromium_dir in chromium_dirs:
                possible_paths = [
                    chromium_dir / "chrome-linux64" / "chrome",
                    chromium_dir / "chrome-linux" / "chrome",
                    chromium_dir / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
                    chromium_dir / "chrome-win" / "chrome.exe",
                ]
                for p in possible_paths:
                    if p.exists() and os.access(p, os.X_OK):
                        return str(p)
                        
        # Fallback to system chrome
        for p in ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']:
            if Path(p).exists() and os.access(p, os.X_OK):
                return p
        
        raise RuntimeError("Chromium browser not found")

    async def _run_singlefile(self, url: str, output_folder: str) -> Dict[str, Any]:
        """Execute SingleFile binary."""
        output_file = os.path.join(output_folder, "singlefile.html")
        
        cmd = [
            self.binary_path,
            "--browser-headless",
            "--max-resource-size-enabled",
            "--max-resource-size", "50",
            "--browser-executable-path", self._chromium_path,
            url,
            output_file,
        ]
        
        project_dir = Path(__file__).resolve().parents[2]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        singlefile_start_time = time_module.time()
        timeout = self.config.app.singlefile_timeout_sec
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
            stdout, stderr = b"", b"SingleFile timed out"
            exit_code = None
            timed_out = True
        
        singlefile_elapsed = time_module.time() - singlefile_start_time
        self.logger.info(f"⏱️ SingleFile subprocess completed in {singlefile_elapsed:.2f}s (exit_code={exit_code}, timed_out={timed_out})")
            
        await self._save_log_to_file(stdout, output_folder, "singlefile_stdout.log")
        await self._save_log_to_file(stderr, output_folder, "singlefile_stderr.log")
        
        return {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "output_file": output_file,
            "stderr": stderr.decode('utf-8', errors='ignore') if stderr else ""
        }

    async def _validate_output(self, output_file: str) -> bool:
        """Return True if the output exists and carries SingleFile's own page markers."""
        path = Path(output_file)
        if not path.exists():
            return False

        try:
            async with aiofiles.open(output_file, "r", encoding="utf-8", errors="ignore") as f:
                content_lower = (await f.read(50000)).lower()
            return "<html" in content_lower and (
                "page saved with singlefile" in content_lower
                or "data-single-file" in content_lower
            )
        except Exception:
            return False

    def _stderr_tail(self, stderr_text: str) -> str:
        """Return the last error line, or the last nonempty stderr line."""
        lines = [line.strip() for line in (stderr_text or "").split("\n") if line.strip()]
        error_lines = [
            line for line in lines if "error" in line.lower() or "fail" in line.lower()
        ]
        if error_lines:
            return error_lines[-1]
        if lines:
            return lines[-1]
        return ""

    def _failure_reason(self, run_result: dict, output_file: str) -> str:
        """Describe a timeout, failed command or missing output."""
        timeout = self.config.app.singlefile_timeout_sec
        if run_result.get("timed_out"):
            return (
                f"SingleFile timed out after {timeout}s "
                "(raise singlefile_timeout_sec for slow/heavy sites)"
            )
        exit_code = run_result.get("exit_code")
        stderr_tail = self._stderr_tail(run_result.get("stderr", ""))
        if exit_code != 0:
            base = f"SingleFile exited with code {exit_code}"
            return f"{base} — {stderr_tail}" if stderr_tail else f"{base} (see singlefile_stderr.log)"
        if not Path(output_file).exists():
            return "SingleFile produced no output file (see singlefile_stderr.log)"
        return (
            "SingleFile output is incomplete/invalid — missing the expected "
            "SingleFile markers (see singlefile_stderr.log)"
        )

    async def generate_archive(
        self,
        url: str,
        output_folder: str,
        requested_artifacts: List[str]
    ) -> List[ArtifactResult]:
        """Generate SingleFile artifact if requested."""
        if "singlefile" not in requested_artifacts:
            return []
            
        try:
            run_result = await self._run_singlefile(url, output_folder)
            output_file = run_result["output_file"]
            
            if run_result["exit_code"] == 0 and await self._validate_output(output_file):
                results = [ArtifactResult(
                    name="singlefile",
                    status=ArtifactStatus.SUCCESS,
                    file_path=output_file,
                    file_size=Path(output_file).stat().st_size
                )]
            else:
                reason = self._failure_reason(run_result, output_file)
                self.logger.warning(f"❌ SingleFile failed: {reason}")
                results = [ArtifactResult(
                    name="singlefile",
                    status=ArtifactStatus.FAILED,
                    error=reason
                )]
            
            return results
        except Exception as e:
            self.logger.error(f"SingleFile generation failed: {e}")
            return [ArtifactResult(name="singlefile", status=ArtifactStatus.FAILED, error=str(e))]
