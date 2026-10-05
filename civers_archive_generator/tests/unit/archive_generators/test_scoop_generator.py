import subprocess
import pytest
from unittest.mock import MagicMock, patch
from archive_generators.scoop.scoop_generator import ScoopGenerator
from archive_generators.archive_result import ArtifactStatus

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.app.scoop_cli_command = "node cli.js"
    config.app.scoop_extra_args = []
    config.app.scoop_timeout_sec = 120
    return config

@pytest.fixture
def scoop_generator(mock_config, monkeypatch):
    monkeypatch.setattr(ScoopGenerator, "_validate_dependencies", lambda self: None)
    return ScoopGenerator(mock_config)

def test_scoop_analyze_artifacts_mapping(scoop_generator, tmp_path):
    # Create mock files in tmp_path
    (tmp_path / "archive.wacz").write_text("wacz content")
    (tmp_path / "screenshot.png").write_text("png content")
    
    requested = ["warc", "screenshot", "dom-snapshot"]
    # dom-snapshot is missing, warc and screenshot exist
    
    results = scoop_generator._analyze_artifacts(str(tmp_path), requested)
    
    assert len(results) == 3
    
    warc_res = next(r for r in results if r.name == "warc")
    assert warc_res.status == ArtifactStatus.SUCCESS
    assert "archive.wacz" in warc_res.file_path
    
    screenshot_res = next(r for r in results if r.name == "screenshot")
    assert screenshot_res.status == ArtifactStatus.SUCCESS
    
    dom_res = next(r for r in results if r.name == "dom-snapshot")
    assert dom_res.status == ArtifactStatus.FAILED
    assert dom_res.error == "Artifact not found"

@pytest.mark.unit
def test_validate_dependencies_names_failing_scoop_cli(mock_config):
    err = subprocess.CalledProcessError(
        1, ["node", "cli.js", "--version"], stderr="Cannot find module '/x/cli.js'"
    )
    with patch("archive_generators.scoop.scoop_generator.subprocess.run", side_effect=err):
        with pytest.raises(ValueError) as exc:
            ScoopGenerator(mock_config)

    message = str(exc.value)
    assert "Scoop CLI" in message
    assert "Cannot find module '/x/cli.js'" in message


@pytest.mark.unit
def test_validate_dependencies_surfaces_runtime_probe_error(mock_config):
    ok = MagicMock(returncode=0, stdout="0.7.0", stderr="")
    err = subprocess.CalledProcessError(
        1, ["node", "-e"], stderr="Playwright chromium is missing at /x/chrome"
    )
    with patch("archive_generators.scoop.scoop_generator.subprocess.run", side_effect=[ok, err]):
        with pytest.raises(ValueError) as exc:
            ScoopGenerator(mock_config)

    message = str(exc.value)
    assert "Node runtime" in message
    assert "Playwright chromium is missing at /x/chrome" in message


@pytest.mark.unit
@pytest.mark.parametrize(
    "cli_command, expected_node",
    [
        ("/usr/bin/node lib/scoop/bin/cli.js", "/usr/bin/node"),
        ("node lib/scoop/bin/cli.js", "node"),
        ("scoop", "node"),
    ],
)
def test_runtime_probe_uses_configured_node_binary(mock_config, cli_command, expected_node):
    mock_config.app.scoop_cli_command = cli_command
    ok = MagicMock(returncode=0, stdout="", stderr="")

    with patch("archive_generators.scoop.scoop_generator.subprocess.run", return_value=ok) as run:
        ScoopGenerator(mock_config)

    assert run.call_count == 2
    cli_cmd = run.call_args_list[0].args[0]
    assert cli_cmd == cli_command.split() + ["--version"]

    probe_cmd = run.call_args_list[1].args[0]
    assert probe_cmd[0] == expected_node
    assert probe_cmd[1] == "-e"


@pytest.mark.asyncio
async def test_scoop_generate_archive_error(scoop_generator):
    with patch.object(ScoopGenerator, "_run_scoop", side_effect=Exception("Scoop crash")):
        results = await scoop_generator.generate_archive("https://example.com", "/tmp", ["warc"])
        assert len(results) == 1
        assert results[0].status == ArtifactStatus.FAILED
        assert results[0].error == "Scoop crash"


@pytest.mark.asyncio
async def test_cancelled_capture_reaps_subprocess(scoop_generator, tmp_path):
    import asyncio
    from unittest.mock import AsyncMock
    process = MagicMock(returncode=None)
    process.communicate = AsyncMock(side_effect=asyncio.CancelledError)
    process.wait = AsyncMock()
    with patch("archive_generators.scoop.scoop_generator.asyncio.create_subprocess_exec", return_value=process):
        with pytest.raises(asyncio.CancelledError):
            await scoop_generator._run_scoop("https://example.com", str(tmp_path), ["screenshot"])
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
