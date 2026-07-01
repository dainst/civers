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
    """
    Archive generator that uses SingleFile to produce a self-contained HTML file.
    Produces: singlefile
    """

    CAPABILITIES = ["singlefile"]

    def __init__(self, config):
        super().__init__(config)
        self._chromium_path = None
        self._validate_dependencies()

    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        try:
            binary_path = self.config.app.singlefile_binary_path
            if not Path(binary_path).exists() or not os.access(binary_path, os.X_OK):
                raise RuntimeError(f"SingleFile binary not found or not executable: {binary_path}")
            
            # Test binary
            subprocess.run([binary_path, "--version"], capture_output=True, text=True, timeout=10, check=True)
            
            # Validate browser
            self._chromium_path = self._get_playwright_chromium_path_sync()
            if not Path(self._chromium_path).exists():
                raise RuntimeError(f"Chromium browser not found at {self._chromium_path}")
        except Exception as e:
            self.logger.error(f"❌ SingleFile dependency validation failed: {e}")
            raise ValueError(f"SingleFile dependencies not available: {e}")

    def _get_playwright_chromium_path_sync(self) -> str:
        """Get the Chromium browser executable path."""
        # Simple extraction from monolith logic
        env_path = os.environ.get('CHROMIUM_PATH')
        if env_path and Path(env_path).exists():
            return env_path
            
        home = Path.home()
        playwright_cache = home / ".cache" / "ms-playwright"
        if playwright_cache.exists():
            chromium_dirs = sorted(playwright_cache.glob("chromium-*"), reverse=True)
            for chromium_dir in chromium_dirs:
                possible_paths = [
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
            self.config.app.singlefile_binary_path,
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
        timeout = max(1, int(self.config.app.singlefile_timeout_sec or 60))
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            exit_code = process.returncode
            timed_out = False
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
        """Basic validation of SingleFile output."""
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
                exit_code = run_result.get("exit_code")
                stderr_text = run_result.get("stderr", "").strip()
                error_msg = "SingleFile execution failed or produced invalid output"
                if stderr_text:
                    lines = [line.strip() for line in stderr_text.split("\n") if line.strip()]
                    error_lines = [l for l in lines if "error" in l.lower() or "fail" in l.lower()]
                    if error_lines:
                        error_msg = f"SingleFile error: {error_lines[-1]}"
                    elif lines:
                        error_msg = f"SingleFile error: {lines[-1]}"
                
                results = [ArtifactResult(
                    name="singlefile",
                    status=ArtifactStatus.FAILED,
                    error=f"SingleFile execution failed (exit={exit_code}). Details: {error_msg}"
                )]
            
            # Results are already mapped in 'results'
            return results
        except Exception as e:
            self.logger.error(f"SingleFile generation failed: {e}")
            return [ArtifactResult(name="singlefile", status=ArtifactStatus.FAILED, error=str(e))]
