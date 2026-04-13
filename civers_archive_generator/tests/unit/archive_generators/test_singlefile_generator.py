import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from archive_generators.singlefile.singlefile_generator import SingleFileGenerator
from archive_generators.archive_result import ArtifactStatus

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.app.singlefile_binary_path = "single-file"
    config.app.singlefile_timeout_sec = 60
    return config

@pytest.fixture
def singlefile_generator(mock_config, monkeypatch):
    monkeypatch.setattr(SingleFileGenerator, "_validate_dependencies", lambda self: None)
    return SingleFileGenerator(mock_config)

@pytest.mark.asyncio
async def test_singlefile_validate_output_valid(singlefile_generator, tmp_path):
    f = tmp_path / "valid.html"
    f.write_text("<html><body>Page saved with SingleFile</body></html>" + "A" * 2000)
    assert await singlefile_generator._validate_output(str(f)) is True

@pytest.mark.asyncio
async def test_singlefile_validate_output_small_but_valid(singlefile_generator, tmp_path):
    # Regression test for small valid archives (e.g., example.com was ~990 bytes)
    # Testing an even smaller file to ensure no hardcoded threshold exists
    f = tmp_path / "tiny_valid.html"
    content = "<html><body>Page saved with SingleFile</body></html>"
    f.write_text(content)
    # Content is only ~50 bytes
    assert len(content) < 100
    assert await singlefile_generator._validate_output(str(f)) is True

@pytest.mark.asyncio
async def test_singlefile_validate_output_invalid(singlefile_generator, tmp_path):
    f = tmp_path / "invalid.html"
    f.write_text("not an archive")
    assert await singlefile_generator._validate_output(str(f)) is False

@pytest.mark.asyncio
async def test_singlefile_generate_archive_success(singlefile_generator, tmp_path):
    output_file = str(tmp_path / "singlefile.html")
    mock_run = {
        "exit_code": 0,
        "timed_out": False,
        "output_file": output_file
    }
    
    with patch.object(singlefile_generator, "_run_singlefile", return_value=mock_run):
        with patch.object(singlefile_generator, "_validate_output", return_value=True):
            Path(output_file).write_text("valid content")
            results = await singlefile_generator.generate_archive("https://example.com", str(tmp_path), ["singlefile"])
            
            assert len(results) == 1
            assert results[0].name == "singlefile"
            assert results[0].status == ArtifactStatus.SUCCESS
