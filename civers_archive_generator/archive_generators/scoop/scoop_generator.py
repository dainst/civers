import asyncio
import time as time_module
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from ..archive_result import ArtifactResult, ArtifactStatus
from ..base_generator import BaseGenerator

class ScoopGenerator(BaseGenerator):
    """
    Archive generator that delegates capture to the Scoop (Node.js) CLI.
    Produces: warc (as WACZ), screenshot, dom-snapshot.
    """

    CAPABILITIES = ["warc", "screenshot", "dom-snapshot", "summary"]

    def __init__(self, config):
        super().__init__(config)
        self._validate_dependencies()

    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        try:
            self._check_nodejs()
            self._check_scoop_cli()
        except Exception as e:
            self.logger.error(f"❌ Scoop dependency validation failed: {e}")
            raise ValueError(f"Scoop dependencies not available: {e}")

    def _check_nodejs(self):
        """Check if Node.js is available."""
        try:
            result = subprocess.run(
                ["node", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10,
                check=True
            )
            self.logger.debug(f"Node.js version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"Node.js not found or not working: {e}")

    def _check_scoop_cli(self):
        """Check if Scoop CLI is accessible."""
        try:
            project_dir = Path(__file__).resolve().parents[2]
            env = os.environ.copy()
            env['PWD'] = str(project_dir)
            
            base_cmd = self.config.app.scoop_cli_command.strip() or "scoop"
            cmd_parts = base_cmd.split()
            
            if cmd_parts[0] == "node" and len(cmd_parts) > 1:
                script_path = project_dir / cmd_parts[1]
                if not script_path.exists():
                    raise RuntimeError(f"Scoop CLI script not found: {script_path}")
                version_cmd = cmd_parts + ["--version"]
                subprocess.run(version_cmd, cwd=str(project_dir), capture_output=True, text=True, timeout=15, check=True, env=env)
            else:
                subprocess.run([base_cmd, "--version"], capture_output=True, text=True, timeout=15, check=True)
        except Exception as e:
            raise RuntimeError(f"Scoop CLI not working: {e}")


    async def _run_scoop(self, url: str, output_folder: str, requested_artifacts: List[str]) -> Dict[str, Any]:
        """Invoke Scoop CLI and save logs to output folder."""
        
        # Determine output format (wacz vs warc)
        output_format = "wacz"
        if "warc" in requested_artifacts and "wacz" not in requested_artifacts:
            output_format = "warc"
        
        output_file = os.path.join(output_folder, f"archive.{output_format}")

        cmd = []
        base_cmd = self.config.app.scoop_cli_command.strip() or "scoop"
        cmd.extend(base_cmd.split())
        cmd += ["-o", output_file, "-f", output_format]
        
        # Dynamic per-request flags (depend on requested artifacts)
        screenshot_flag = "true" if "screenshot" in requested_artifacts else "false"
        dom_snapshot_flag = "true" if "dom-snapshot" in requested_artifacts else "false"
        
        cmd += [
            "--screenshot", screenshot_flag,
            "--dom-snapshot", dom_snapshot_flag,
            "--export-attachments-output", output_folder,
        ]

        if "summary" in requested_artifacts:
            cmd += ["--json-summary-output", os.path.join(output_folder, "summary.json")]
        
        # Static default flags from config (timeouts, features, log-level, etc.)
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

        timeout = max(1, int(self.config.app.scoop_timeout_sec or 120))
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            exit_code = process.returncode
            timed_out = False
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
        """Analyze Scoop output and map to requested artifacts."""
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
        """Orchestrate Scoop capture and return artifact results."""
        try:
            # Scoop needs to run once regardless of which of its 3 capabilities are requested
            # because it produces WACZ/WARC, screenshot, and DOM in one go.
            run_result = await self._run_scoop(url, output_folder, requested_artifacts)
            
            # Map requested artifacts to Scoop output
            artifacts = self._analyze_artifacts(output_folder, requested_artifacts)
            
            # If Scoop exited with an error, append details to failed artifacts
            exit_code = run_result.get("exit_code")
            if exit_code is not None and exit_code != 0:
                stderr_text = run_result.get("stderr", "").strip()
                error_msg = "Scoop subprocess failed"
                if stderr_text:
                    lines = [line.strip() for line in stderr_text.split("\n") if line.strip()]
                    error_lines = [l for l in lines if "error" in l.lower() or "fail" in l.lower()]
                    if error_lines:
                        error_msg = f"Scoop error: {error_lines[-1]}"
                    elif lines:
                        error_msg = f"Scoop error: {lines[-1]}"
                
                # Update failed artifacts with the error message
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
