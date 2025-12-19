import asyncio
import os
import json
import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional
from pathlib import Path
import shutil
import socket
import subprocess

from configs.models import ConfigDataModel
from archive_generators import ArchiveGeneratorStrategyInterface

logger = logging.getLogger(__name__)


class ScoopArchiveGeneratorStrategy(ArchiveGeneratorStrategyInterface):
    """
    Archive generator that delegates capture to the Scoop (Node.js) CLI.

    Responsibilities:
    - Create a structured archive output directory
    - Invoke Scoop via subprocess with configured command and arguments
    - Persist stdout/stderr logs for traceability
    - Generate metadata.json summarizing the run and artifacts
    """

    def __init__(self, config: ConfigDataModel):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._chromium_path = None  # Cache for browser path
        self._validate_config()
        self._validate_dependencies()

    def _validate_config(self):
        if not self.config.app.archive_directory:
            raise ValueError("Archive directory must be specified in configuration")
        # scoop_cli_command can be defaulted to 'scoop'; warn if looks empty
        if not self.config.app.scoop_cli_command:
            self.logger.warning("scoop_cli_command is empty; defaulting to 'scoop'")

    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        try:
            # Check if Node.js is available
            self._check_nodejs()
            
            # Check if Scoop CLI is accessible
            self._check_scoop_cli()
            
            # Check if SingleFile binary is available
            self._check_singlefile_binary()
            
            self.logger.info("✅ All dependencies verified successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Dependency validation failed: {e}")
            raise ValueError(f"Dependencies not available: {e}")

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
            node_version = result.stdout.strip()
            self.logger.debug(f"Node.js version: {node_version}")
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Node.js not working properly (exit code {e.returncode})")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Node.js command timed out")
        except FileNotFoundError:
            raise RuntimeError("Node.js not found. Please install Node.js 20+ to use Scoop archiving.")

    def _check_scoop_cli(self):
        """Check if Scoop CLI is accessible."""
        try:
            # Get project directory and verify Scoop CLI files exist
            project_dir = Path(__file__).resolve().parents[1]
            
            # Build environment with PWD set (required by Scoop CLI)
            env = os.environ.copy()
            env['PWD'] = str(project_dir)
            
            # Check the default command structure
            base_cmd = self.config.app.scoop_cli_command.strip() or "scoop"
            cmd_parts = base_cmd.split()
            
            if cmd_parts[0] == "node" and len(cmd_parts) > 1:
                # This is a node command, check if the script file exists
                script_path = project_dir / cmd_parts[1]
                if not script_path.exists():
                    raise RuntimeError(f"Scoop CLI script not found: {script_path}")
                self.logger.debug(f"Scoop CLI script found: {script_path}")
                
                # Try to get Scoop version
                version_cmd = cmd_parts + ["--version"]
                result = subprocess.run(
                    version_cmd,
                    cwd=str(project_dir),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                    env=env
                )
                scoop_version = result.stdout.strip()
                self.logger.debug(f"Scoop CLI version: {scoop_version}")

                
            else:
                # This might be a system-wide scoop command
                result = subprocess.run(
                    [base_cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True
                )
                scoop_version = result.stdout.strip()
                self.logger.debug(f"Scoop CLI version: {scoop_version}")
                
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Scoop CLI not working properly (exit code {e.returncode})")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Scoop CLI command timed out")
        except FileNotFoundError:
            raise RuntimeError(f"Scoop CLI command not found: {base_cmd}")
        except Exception as e:
            raise RuntimeError(f"Failed to verify Scoop CLI: {e}")

    def _check_singlefile_binary(self):
        """Check if SingleFile binary is available and executable."""
        try:
            binary_path = self.config.app.singlefile_binary_path
            self.logger.debug(f"Validating SingleFile binary at: {binary_path}")

            if not Path(binary_path).exists():
                self.logger.error(f"SingleFile binary not found at path: {binary_path}")
                raise RuntimeError(f"SingleFile binary not found: {binary_path}")

            # Check if binary is executable
            if not os.access(binary_path, os.X_OK):
                self.logger.error(f"SingleFile binary exists but is not executable: {binary_path}")
                raise RuntimeError(f"SingleFile binary not executable: {binary_path}")

            # Test binary functionality with --version command
            self.logger.debug("Testing SingleFile binary functionality with --version")
            result = subprocess.run(
                [binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            singlefile_version = result.stdout.strip()
            self.logger.info(f"✅ SingleFile binary validated - version: {singlefile_version}")

            # Validate browser availability for SingleFile
            self._validate_browser_for_singlefile()

        except subprocess.CalledProcessError as e:
            error_msg = f"SingleFile binary not working properly (exit code {e.returncode})"
            self.logger.error(f"❌ {error_msg}")
            if e.stderr:
                self.logger.error(f"SingleFile binary stderr: {e.stderr.strip()}")
            raise RuntimeError(error_msg)
        except subprocess.TimeoutExpired:
            error_msg = "SingleFile binary version check timed out"
            self.logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        except FileNotFoundError:
            error_msg = f"SingleFile binary not found or not executable: {binary_path}"
            self.logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Failed to validate SingleFile binary: {e}"
            self.logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

    def _validate_browser_for_singlefile(self):
        """Validate that a compatible browser is available for SingleFile."""
        try:
            browser_path = self._get_playwright_chromium_path_sync()

            if not Path(browser_path).exists():
                raise RuntimeError(
                    f"Browser not found at: {browser_path}\n"
                    f"Please run: uv run playwright install chromium"
                )

            # Cache the browser path for later use in async context
            self._chromium_path = browser_path
            self.logger.info(f"✅ Browser validated for SingleFile: {browser_path}")

        except Exception as e:
            error_msg = (
                f"Browser validation failed: {e}\n"
                f"SingleFile requires a Chromium browser. Please run:\n"
                f"  uv run playwright install chromium\n"
                f"Or ensure Chrome/Chromium is installed on your system."
            )
            self.logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

    def _get_domain_config_for_url(self, url: str):
        """Get domain configuration for a given URL."""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Search through configured domains
            for domain_config in self.config.domains:
                if (domain == domain_config.name.lower() or 
                    domain.endswith(f".{domain_config.name.lower()}") or
                    domain_config.name.lower() in domain):
                    return domain_config
            
            self.logger.debug(f"No domain config found for URL: {url}")
            return None
            
        except Exception as e:
            self.logger.warning(f"Error parsing URL {url}: {e}")
            return None

    def _should_generate_singlefile(self, domain_config) -> bool:
        """Determine if SingleFile HTML should be generated for this domain."""
        if not domain_config:
            self.logger.debug("No domain config provided, skipping SingleFile generation")
            return False

        if "singlefile" not in domain_config.artifacts:
            self.logger.debug(f"SingleFile not requested for domain {domain_config.name}")
            return False

        self.logger.debug(f"SingleFile generation requested for domain {domain_config.name}")
        return True

    def _get_playwright_chromium_path_sync(self) -> str:
        """
        Get the Chromium browser executable path (sync version for initialization).

        This method should only be called during initialization (non-async context).
        For async contexts, the path is cached in self._chromium_path.

        Priority order:
        1. Environment variable CHROMIUM_PATH (allows override)
        2. Playwright's managed Chromium (recommended, portable)
        3. System Chrome/Chromium installations

        Returns:
            str: Path to Chromium executable

        Raises:
            RuntimeError: If no suitable browser is found
        """
        # Check environment variable first (allows override)
        env_chromium_path = os.environ.get('CHROMIUM_PATH')
        if env_chromium_path:
            env_path = Path(env_chromium_path)
            if env_path.exists() and os.access(env_path, os.X_OK):
                self.logger.debug(f"Using Chromium from CHROMIUM_PATH: {env_chromium_path}")
                return env_chromium_path
            else:
                self.logger.warning(
                    f"CHROMIUM_PATH set to '{env_chromium_path}' but path does not exist or is not executable"
                )

        # Try Playwright's managed Chromium (preferred method)
        # We need to get this without starting an async context
        try:
            # Instead of using Playwright API, directly check the cache directory
            home = Path.home()
            playwright_cache = home / ".cache" / "ms-playwright"

            if playwright_cache.exists():
                # Find chromium directories
                chromium_dirs = sorted(playwright_cache.glob("chromium-*"), reverse=True)

                for chromium_dir in chromium_dirs:
                    # Check common paths for the chrome executable
                    possible_paths = [
                        chromium_dir / "chrome-linux" / "chrome",  # Linux
                        chromium_dir / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",  # macOS
                        chromium_dir / "chrome-win" / "chrome.exe",  # Windows
                    ]

                    for chrome_path in possible_paths:
                        if chrome_path.exists() and os.access(chrome_path, os.X_OK):
                            self.logger.debug(f"Using Playwright Chromium: {chrome_path}")
                            return str(chrome_path)

                self.logger.warning(
                    f"Playwright cache found at {playwright_cache} but no valid Chromium installation. "
                    f"Run 'uv run playwright install chromium' to install."
                )
            else:
                self.logger.warning(
                    f"Playwright cache not found at {playwright_cache}. "
                    f"Run 'uv run playwright install chromium' to install."
                )

        except Exception as e:
            self.logger.warning(f"Failed to detect Playwright Chromium: {e}")

        # Fallback to system Chrome/Chromium installations
        system_browsers = [
            '/usr/bin/google-chrome',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',  # Windows
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',  # Windows 32-bit
        ]

        for chrome_path in system_browsers:
            if Path(chrome_path).exists() and os.access(chrome_path, os.X_OK):
                self.logger.warning(
                    f"Using system Chrome/Chromium: {chrome_path}. "
                    f"For better portability, install Playwright browsers: uv run playwright install chromium"
                )
                return chrome_path

        # If nothing works, raise an error with helpful message
        raise RuntimeError(
            "No Chromium browser found for SingleFile.\n"
            "Please install Playwright browsers:\n"
            "  uv run playwright install chromium\n"
            "\n"
            "Alternatively, you can:\n"
            "1. Install Chrome/Chromium on your system\n"
            "2. Set CHROMIUM_PATH environment variable to your browser executable\n"
            "\n"
            "For portable deployment, Playwright browsers are recommended."
        )

    async def _run_singlefile(self, url: str, output_folder: str) -> Dict[str, Any]:
        """Execute SingleFile binary to generate self-contained HTML."""
        stdout_log = os.path.join(output_folder, "singlefile_stdout.log")
        stderr_log = os.path.join(output_folder, "singlefile_stderr.log")
        output_file = os.path.join(output_folder, "singlefile.html")

        try:
            # Use cached browser path (set during initialization)
            browser_path = self._chromium_path
            if not browser_path:
                raise RuntimeError("Browser path not initialized. This should not happen.")

            # Build SingleFile command
            cmd = [
                self.config.app.singlefile_binary_path,
                url,
                output_file,
                "--browser-headless",
                "--max-resource-size-enabled",
                "--max-resource-size", "50",  # 50MB limit per resource
                "--browser-executable-path", browser_path
            ]
            
            self.logger.info(f"Executing SingleFile for URL: {url}")
            self.logger.debug(f"SingleFile command: {' '.join(cmd)}")
            self.logger.debug(f"Output file: {output_file}")
            
            # Execute with timeout
            start_time = datetime.now()
            
            # Run from the project directory for consistency with Scoop execution
            project_dir = Path(__file__).resolve().parents[1]
            self.logger.debug(f"Executing from directory: {project_dir}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                timeout = max(1, int(self.config.app.singlefile_timeout_sec))
                self.logger.debug(f"SingleFile timeout set to: {timeout} seconds")
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                exit_code = process.returncode
                timed_out = False
                
                if exit_code == 0:
                    self.logger.debug("SingleFile process completed successfully")
                else:
                    self.logger.warning(f"SingleFile process completed with non-zero exit code: {exit_code}")
                    if stderr:
                        self.logger.warning(f"SingleFile stderr: {stderr.decode('utf-8', errors='ignore')[:500]}")
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"SingleFile process timed out after {timeout} seconds")
                process.kill()
                await process.wait()
                stdout, stderr = b"", f"SingleFile process timed out after {timeout} seconds".encode()
                exit_code = None
                timed_out = True
            
            # Save logs with error handling
            try:
                Path(stdout_log).write_bytes(stdout or b"")
                self.logger.debug(f"Saved SingleFile stdout to: {stdout_log}")
            except Exception as e:
                self.logger.error(f"Failed to save SingleFile stdout log: {e}")
                
            try:
                Path(stderr_log).write_bytes(stderr or b"")
                self.logger.debug(f"Saved SingleFile stderr to: {stderr_log}")
            except Exception as e:
                self.logger.error(f"Failed to save SingleFile stderr log: {e}")
            
            # Return execution metadata
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            result = {
                "exit_code": exit_code,
                "timed_out": timed_out,
                "output_file": output_file,
                "execution_time_sec": execution_time,
                "stdout_log": stdout_log,
                "stderr_log": stderr_log,
                "url": url,
                "command": ' '.join(cmd)
            }
            
            self.logger.debug(f"SingleFile execution completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ SingleFile execution failed with exception: {e}")
            # Still try to save any available logs
            try:
                if 'stdout_log' in locals():
                    Path(stdout_log).write_bytes(f"SingleFile execution failed: {e}".encode())
                if 'stderr_log' in locals():
                    Path(stderr_log).write_bytes(f"SingleFile execution failed: {e}".encode())
            except:
                pass
            raise

    def _validate_singlefile_output(self, output_file: str) -> Dict[str, Any]:
        """Validate that SingleFile generated valid HTML output."""
        validation_result = {
            "valid": False,
            "file_exists": False,
            "file_size": 0,
            "has_html_structure": False,
            "has_singlefile_markers": False,
            "errors": []
        }
        
        try:
            # Check file exists
            if not Path(output_file).exists():
                validation_result["errors"].append("Output file does not exist")
                return validation_result
            validation_result["file_exists"] = True
            
            # Check file size
            file_size = Path(output_file).stat().st_size
            validation_result["file_size"] = file_size
            if file_size < 1024:  # Less than 1KB is suspicious
                validation_result["errors"].append(f"Output file too small: {file_size} bytes")
            
            # Check HTML structure
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Read first 10KB
                
            # Check for basic HTML structure (more flexible)
            content_lower = content.lower()
            if ('<html' in content_lower and 
                ('</head>' in content_lower or '<meta' in content_lower) and 
                '<body' in content_lower):
                validation_result["has_html_structure"] = True
            else:
                validation_result["errors"].append("Invalid HTML structure")
            
            # Check for SingleFile markers (look for "Page saved with SingleFile" comment)
            if ('page saved with singlefile' in content_lower or 
                'single-file' in content_lower or 
                'data-single-file' in content):
                validation_result["has_singlefile_markers"] = True
            else:
                validation_result["errors"].append("Missing SingleFile markers")
            
            # Overall validation
            validation_result["valid"] = (
                validation_result["file_exists"] and
                file_size >= 1024 and
                validation_result["has_html_structure"] and
                len(validation_result["errors"]) == 0
            )
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
        
        return validation_result

    async def generate_archive(self, url: str, request_id: str) -> str:
        start_time = datetime.now()
        self.logger.info(f"Starting Scoop archive for: {url}")

        output_folder = self._create_output_folder(url, request_id)
        self.logger.info(f"Archive directory: {output_folder}")

        results: Dict[str, Any] = {}

        # Run Scoop and capture stdout/stderr
        try:
            run_result = await self._run_scoop(url, output_folder)
            results["scoop_run"] = run_result
        except Exception as e:
            self.logger.error(f"Scoop run failed: {e}")
            results["scoop_run"] = {
                "error": str(e),
                "exit_code": None,
            }

        # Run SingleFile if requested
        domain_config = self._get_domain_config_for_url(url)
        if self._should_generate_singlefile(domain_config):
            self.logger.info(f"SingleFile requested for domain: {domain_config.name if domain_config else 'unknown'}")
            try:
                self.logger.info("🔄 Starting SingleFile HTML generation")
                singlefile_result = await self._run_singlefile(url, output_folder)
                
                # Validate SingleFile output
                self.logger.debug("Validating SingleFile output")
                validation_result = self._validate_singlefile_output(singlefile_result["output_file"])
                singlefile_result["validation"] = validation_result
                
                results["singlefile_run"] = singlefile_result
                
                # Enhanced logging based on results
                if singlefile_result["exit_code"] == 0:
                    if validation_result["valid"]:
                        file_size = validation_result.get("file_size", 0)
                        execution_time = singlefile_result.get("execution_time_sec", 0)
                        self.logger.info(f"✅ SingleFile HTML generated successfully ({file_size:,} bytes, {execution_time:.2f}s)")
                    else:
                        error_summary = ", ".join(validation_result.get('errors', ['validation failed']))
                        self.logger.warning(f"⚠️ SingleFile generated but validation failed: {error_summary}")
                        self.logger.debug(f"Full validation result: {validation_result}")
                elif singlefile_result.get("timed_out"):
                    timeout = self.config.app.singlefile_timeout_sec
                    self.logger.warning(f"⚠️ SingleFile process timed out after {timeout} seconds")
                else:
                    exit_code = singlefile_result.get('exit_code', 'unknown')
                    self.logger.warning(f"⚠️ SingleFile completed with exit code {exit_code}")
                    
                    # Log stderr if available for debugging
                    stderr_log = singlefile_result.get("stderr_log")
                    if stderr_log and os.path.exists(stderr_log):
                        try:
                            with open(stderr_log, 'r', encoding='utf-8', errors='ignore') as f:
                                stderr_content = f.read(1000).strip()
                            if stderr_content:
                                self.logger.debug(f"SingleFile stderr: {stderr_content}")
                        except Exception:
                            pass
                    
            except Exception as e:
                error_type = type(e).__name__
                self.logger.error(f"❌ SingleFile generation failed with {error_type}: {e}")
                
                # Create error result with structured information
                results["singlefile_run"] = {
                    "error": str(e),
                    "error_type": error_type,
                    "exit_code": None,
                    "timed_out": False,
                    "execution_time_sec": None,
                    "validation": {
                        "valid": False,
                        "errors": [f"Execution failed: {e}"]
                    }
                }
                
                # Log additional context for debugging
                import traceback
                self.logger.debug(f"SingleFile exception traceback: {traceback.format_exc()}")
        else:
            self.logger.debug("SingleFile generation not requested for this domain")

        # Generate metadata
        metadata = self._generate_metadata(url, output_folder, start_time, results, request_id)
        self._save_metadata(metadata, output_folder)

        self.logger.info(f"Archive generation completed: {output_folder}")
        return output_folder

    def _create_output_folder(self, url: str, request_id: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "_").replace("-", "_")
        path_part = parsed.path.strip("/").replace("/", "_").replace("-", "_")
        if not path_part:
            path_part = "home_page"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = os.path.join(
            self.config.app.archive_directory,
            domain,
            path_part,
            f"req_{request_id}_{timestamp}"
        )
        os.makedirs(output_folder, exist_ok=True)
        return output_folder

    async def _run_scoop(self, url: str, output_folder: str) -> Dict[str, Any]:
        """Invoke Scoop CLI and save logs to output folder."""
        stdout_log = os.path.join(output_folder, "scoop_stdout.log")
        stderr_log = os.path.join(output_folder, "scoop_stderr.log")

        # Determine output format and file
        # Default to warc-gzipped unless overridden via extra args
        output_format = "wacz"
        output_file = os.path.join(output_folder, "archive.wacz")

        # Build command per Scoop CLI
        cmd: List[str] = []
        base_cmd = self.config.app.scoop_cli_command.strip() or "scoop"
        cmd.extend(base_cmd.split())

        # URL first
        cmd.append(url)
        # Output and format
        cmd += ["-o", output_file, "-f", output_format]
        # Optional outputs
        cmd += [
            "--json-summary-output", os.path.join(output_folder, "summary.json"),
            "--export-attachments-output", output_folder,
            "--log-level", "info",
        ]
        # Allow extra args from config to extend/override (we will override proxy settings after this)
        if self.config.app.scoop_extra_args:
            cmd += list(self.config.app.scoop_extra_args)

        # Pick a free TCP port for the proxy and force localhost IPv4
        free_port = self._find_free_port()
        cmd += ["--proxy-host", "127.0.0.1", "--proxy-port", str(free_port)]

        self.logger.debug(f"Running Scoop command: {' '.join(cmd)}")

        # Run from the project directory so relative paths in scoop_cli_command work
        # Use dynamic path resolution that works both locally and in Docker
        project_dir = Path(__file__).resolve().parents[1]
        
        # Verify the project directory exists
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        
        self.logger.debug(f"Running Scoop from directory: {project_dir}")

        # Build environment with PWD set (required by Scoop CLI)
        env = os.environ.copy()
        env['PWD'] = str(project_dir)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )


        try:
            timeout = max(1, int(self.config.app.scoop_timeout_sec))
        except Exception:
            timeout = 120

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            stdout, stderr = b"", b"Scoop process timed out"
            exit_code = None
            timed_out = True
        else:
            exit_code = process.returncode
            timed_out = False

        # Write logs
        Path(stdout_log).write_bytes(stdout or b"")
        Path(stderr_log).write_bytes(stderr or b"")

        result = {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout_log": stdout_log,
            "stderr_log": stderr_log,
            "output_file": output_file,
            "format": output_format,
        }
        if exit_code not in (0, None):
            self.logger.warning(f"Scoop exited with code {exit_code}")

        return result

    def _find_free_port(self) -> int:
        """Find an available TCP port on localhost."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        _, port = sock.getsockname()
        sock.close()
        return int(port)

    def _generate_metadata(self, url: str, output_folder: str, start_time: datetime, results: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        end_time = datetime.now()
        files = []
        for file_path in Path(output_folder).iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'name': file_path.name,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        scoop_result = results.get("scoop_run", {})
        singlefile_result = results.get("singlefile_run", {})
        metadata = {
            'archive_info': {
                'url': url,
                'request_id': request_id,
                'created_at': start_time.isoformat(),
                'completed_at': end_time.isoformat(),
                'processing_time_seconds': (end_time - start_time).total_seconds(),
                'generator': 'ScoopArchiveGeneratorStrategy',
                'version': '1.0.0'
            },
            'config': {
                'archive_directory': self.config.app.archive_directory,
                'scoop_cli_command': self.config.app.scoop_cli_command,
                'scoop_timeout_sec': self.config.app.scoop_timeout_sec,
                'singlefile_binary_path': self.config.app.singlefile_binary_path,
                'singlefile_timeout_sec': self.config.app.singlefile_timeout_sec,
            },
            'results': {
                'scoop_exit_code': scoop_result.get('exit_code'),
                'scoop_timed_out': scoop_result.get('timed_out', False),
                'singlefile_exit_code': singlefile_result.get('exit_code'),
                'singlefile_timed_out': singlefile_result.get('timed_out', False),
                'singlefile_execution_time_sec': singlefile_result.get('execution_time_sec'),
                'singlefile_validation': singlefile_result.get('validation'),
                'artifacts_created': [f['name'] for f in files]
            },
            'files': files
        }
        return metadata

    def _save_metadata(self, metadata: Dict[str, Any], output_folder: str):
        meta_path = os.path.join(output_folder, "metadata.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
