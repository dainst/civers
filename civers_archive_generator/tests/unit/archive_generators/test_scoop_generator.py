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

@pytest.mark.asyncio
async def test_scoop_generate_archive_error(scoop_generator):
    with patch.object(ScoopGenerator, "_run_scoop", side_effect=Exception("Scoop crash")):
        results = await scoop_generator.generate_archive("https://example.com", "/tmp", ["warc"])
        assert len(results) == 1
        assert results[0].status == ArtifactStatus.FAILED
        assert results[0].error == "Scoop crash"
