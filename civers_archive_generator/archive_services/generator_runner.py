"""Runs a domain's generators and collects what each produced."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, List, Tuple

from archive_generators import ArtifactResult, ArtifactStatus
from configs.models import DomainConfig

logger = logging.getLogger(__name__)


@dataclass
class GeneratorRunOutcome:
    """Artifacts, timing and problems reported by a generator run."""

    artifacts: List[ArtifactResult] = field(default_factory=list)
    timings: List[Tuple[str, float]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    skipped_generators: List[str] = field(default_factory=list)

    @property
    def problems(self) -> List[str]:
        """Combine capture errors and unavailable-generator messages."""
        return list(self.errors) + [
            f"{name}: generator not available" for name in self.skipped_generators
        ]

    @property
    def success(self) -> bool:
        """True when no generator reported an error. Missing outputs are checked separately."""
        return not self.errors


class GeneratorRunner:
    """Run generators in order and continue after capture failures."""

    async def run_all(
        self,
        url: str,
        output_folder: str,
        domain_config: DomainConfig,
        generators: List[Any],
    ) -> GeneratorRunOutcome:
        """Run the supplied (config, generator) pairs in order.

        Record unavailable generators and capture errors without stopping later captures.
        """
        outcome = GeneratorRunOutcome()

        available = {config.name for config, _ in generators}
        outcome.skipped_generators = [
            config.name for config in domain_config.generators if config.name not in available
        ]
        for gen_config, generator in generators:
            logger.info(f"📦 Running {gen_config.name} generator for {url}")
            gen_start = time.time()
            try:
                artifact_results = await generator.generate_archive(url, output_folder, gen_config.artifacts)
                gen_elapsed = time.time() - gen_start
                outcome.timings.append((gen_config.name, gen_elapsed))
                logger.info(f"⏱️ {gen_config.name} generator completed in {gen_elapsed:.2f}s")
                outcome.artifacts.extend(artifact_results)

                for artifact in artifact_results:
                    if artifact.status == ArtifactStatus.FAILED:
                        outcome.errors.append(f"{gen_config.name}: {artifact.name} failed - {artifact.error}")
            except Exception as e:
                gen_elapsed = time.time() - gen_start
                outcome.timings.append((gen_config.name, gen_elapsed))
                logger.error(f"❌ {gen_config.name} generator failed after {gen_elapsed:.2f}s: {e}")
                outcome.errors.append(f"{gen_config.name} catastrophic failure: {e}")

        return outcome
