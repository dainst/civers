"""Running each configured generator and collecting artifacts, timings and errors."""

from unittest.mock import AsyncMock

import pytest
from archive_generators.archive_result import ArtifactResult, ArtifactStatus
from archive_services.generator_runner import GeneratorRunner
from configs.models import DomainConfig


def _generator(artifacts=None, error=None):
    generator = AsyncMock()
    if error is not None:
        generator.generate_archive.side_effect = error
    else:
        generator.generate_archive.return_value = artifacts or []
    return generator


@pytest.fixture
def runner():
    return GeneratorRunner()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collects_artifacts_and_reports_success(runner, sample_config):
    domain_config = sample_config.domains[0]
    generator = _generator(
        [ArtifactResult("warc", ArtifactStatus.SUCCESS, "/tmp/a.warc", 10)],
    )

    outcome = await runner.run_all(
        "https://example.com",
        "/tmp/out",
        domain_config,
        [(domain_config.generators[0], generator)],
    )

    assert outcome.success is True
    assert [a.name for a in outcome.artifacts] == ["warc"]
    assert outcome.errors == []
    assert [name for name, _ in outcome.timings] == ["scoop"]
    generator.generate_archive.assert_awaited_once_with(
        "https://example.com", "/tmp/out", domain_config.generators[0].artifacts
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_artifact_marks_run_unsuccessful(runner, sample_config):
    domain_config = sample_config.domains[0]
    generator = _generator(
        [ArtifactResult("warc", ArtifactStatus.FAILED, None, 0, "disk full")],
    )

    outcome = await runner.run_all(
        "https://example.com",
        "/tmp/out",
        domain_config,
        [(domain_config.generators[0], generator)],
    )

    assert outcome.success is False
    assert outcome.errors == ["scoop: warc failed - disk full"]
    assert len(outcome.artifacts) == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True], ids=["failed-artifact", "exception"])
async def test_failed_generator_does_not_prevent_later_capture(runner, raises):
    domain_config = DomainConfig(
        name="example.com",
        webpage_types="dynamic",
        generators=[
            {"name": "scoop", "artifacts": ["warc"]},
            {"name": "singlefile", "artifacts": ["singlefile"]},
        ],
    )
    failed = _generator(
        artifacts=[
            ArtifactResult("warc", ArtifactStatus.FAILED, None, 0, "capture crashed")
        ],
        error=RuntimeError("capture crashed") if raises else None,
    )
    captured = ArtifactResult(
        "singlefile", ArtifactStatus.SUCCESS, "/tmp/page.html", 10
    )
    later = _generator([captured])

    outcome = await runner.run_all(
        "https://example.com",
        "/tmp/out",
        domain_config,
        [(domain_config.generators[0], failed), (domain_config.generators[1], later)],
    )

    assert outcome.success is False
    assert len(outcome.errors) == 1
    assert "scoop" in outcome.errors[0]
    assert "capture crashed" in outcome.errors[0]
    assert captured in outcome.artifacts
    assert [name for name, _ in outcome.timings] == ["scoop", "singlefile"]
    later.generate_archive.assert_awaited_once_with(
        "https://example.com", "/tmp/out", ["singlefile"]
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_configured_generator_that_is_missing_is_recorded(
    runner, sample_config
):
    """A configured generator that cannot be built is recorded, not skipped in silence."""
    domain_config = sample_config.domains[0]

    outcome = await runner.run_all("https://example.com", "/tmp/out", domain_config, [])

    assert outcome.artifacts == []
    assert outcome.timings == []
    assert outcome.skipped_generators == ["scoop"]
    assert outcome.problems == ["scoop: generator not available"]
    assert outcome.errors == [], "nothing ran, so nothing reported a failure"
