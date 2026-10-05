"""Capture a page, save metadata and publish its files."""

import logging
import time
from datetime import datetime
from typing import List


from civers_common import ConfigurationError, Result

from configs.models import ConfigDataModel, DomainConfig
from domain.commands import ArchiveCommand
from .archive_service_interface import ArchiveServiceInterface
from .archive_metadata import ArchiveMetadata
from .archive_workspace import ArchiveWorkspace
from .generator_runner import GeneratorRunner
from .url_guard import UrlGuard
from archive_generators import ArchiveGeneratorFactory, ArtifactResult, ArtifactStatus
from storage_layer import StorageManager
from storage_layer.storage_strategy import MultiStorageResult

logger = logging.getLogger(__name__)

class ArchiveService(ArchiveServiceInterface):
    """Coordinate captures for commands from any supported transport."""


    def __init__(self, config: ConfigDataModel):
        self.config = config
        self.generator_factory = ArchiveGeneratorFactory(config)
        self.url_guard = UrlGuard()
        self.archive_metadata = ArchiveMetadata()
        self.generator_runner = GeneratorRunner()

        self.storage = StorageManager(config.app.get_storage_config())

    async def execute(self, command: ArchiveCommand) -> Result:
        """Run the archive command and return its Result."""
        return await self.create_archive(command.url, command.request_id)

    def _failure_result(self, start_time: datetime, error: str, error_type: str) -> Result:
        """Return an early failure with the same data fields as a capture failure."""
        return Result.fail(
            error,
            error_type,
            archive_path=None,
            artifacts_created=[],
            failed_artifacts=[],
            missing_artifacts=[],
            skipped_generators=[],
            processing_time_seconds=(datetime.now() - start_time).total_seconds(),
        )

    @staticmethod
    def _missing_artifacts(domain_config: DomainConfig, artifacts: List[ArtifactResult]) -> List[str]:
        """Return requested artifact names that no generator reported."""
        produced = {a.name for a in artifacts}
        requested = [a for g in domain_config.generators for a in g.artifacts]
        return [name for name in dict.fromkeys(requested) if name not in produced]

    async def create_archive(self, url: str, request_id: str) -> Result:
        """Create an archive for the given URL by running each configured generator."""
        start_time = datetime.now()

        logger.info(f"🚀 Starting archive creation for request: {request_id}")
        logger.info(f"   URL: {url}")

        try:
            try:
                domain_config = self.config.resolve_domain_for_url(url)
            except ConfigurationError as e:
                logger.warning(f"⚠️ {e}")
                return self._failure_result(
                    start_time, str(e), 'configuration_not_found'
                )

            logger.info(f"✅ Found domain config: {domain_config.name}")

            if self.config.app.ssrf_protection_enabled:
                try:
                    await self.url_guard.validate(url)
                except ValueError as e:
                    logger.error(f"🚨 SSRF Protection: {e}")
                    return self._failure_result(
                        start_time, str(e), 'ssrf_blocked'
                    )
            else:
                logger.warning(f"⚠️ SSRF protection is disabled — skipping IP check for: {url}")

            workspace = await ArchiveWorkspace.open(self.config, url, request_id)
            output_folder = str(workspace.path)
            logger.info(f"📂 Archive directory: {output_folder}")

            generators = self.generator_factory.create_generators(domain_config)
            logger.info(f"🔧 Initialized {len(generators)} archive generators")

            outcome = await self.generator_runner.run_all(url, output_folder, domain_config, generators)
            all_artifacts = outcome.artifacts
            error_messages = outcome.problems
            generator_timings = outcome.timings

            meta_start = time.time()
            generator_info = [
                {"name": generator.get_generator_name(),
                 "capabilities": ",".join(generator.get_capabilities())}
                for _, generator in generators
            ]
            # Inventory before writing metadata so the record does not list itself.
            bundle = await workspace.inventory()
            capture_time = (datetime.now() - start_time).total_seconds()
            metadata = self.archive_metadata.build(
                bundle, all_artifacts, start_time, capture_time, generator_info=generator_info
            )
            await self.archive_metadata.save(metadata, output_folder)
            # Include the metadata file in the upload.
            bundle = bundle.add(
                await workspace.stat_one(self.archive_metadata.FILENAME)
            )
            meta_elapsed = time.time() - meta_start

            storage_start = time.time()
            # Upload failure must not discard a successful local capture.
            try:
                publication = await self.storage.publish(bundle)
                published = True
            except Exception as storage_error:
                logger.warning(f"⚠️ Storage error (continuing anyway): {storage_error}")
                publication = MultiStorageResult(overall_success=False, results=[])
                published = False

            storage_elapsed = time.time() - storage_start
            if published:
                logger.info(f"💾 Archive stored successfully ({storage_elapsed:.2f}s)")

            processing_time = (datetime.now() - start_time).total_seconds()
            snapshot_id = publication.snapshot_id() or workspace.snapshot_id
            created = [a.name for a in all_artifacts if a.status == ArtifactStatus.SUCCESS]
            failed = [a.name for a in all_artifacts if a.status == ArtifactStatus.FAILED]
            # Compare with requested outputs to catch skipped or incomplete generators.
            missing = self._missing_artifacts(domain_config, all_artifacts)
            skipped = outcome.skipped_generators
            incomplete = bool(failed or missing or skipped)

            if created:
                if incomplete:
                    logger.warning(
                        f"⚠️ Partial archive for {request_id}: "
                        f"created={created} failed={failed} missing={missing} "
                        f"skipped_generators={skipped}"
                    )
                build = Result.partial if incomplete else Result.ok
                result = build(
                    request_id=request_id,
                    url=url,
                    archive_path=output_folder,
                    artifacts_created=created,
                    failed_artifacts=failed,
                    missing_artifacts=missing,
                    skipped_generators=skipped,
                    processing_time_seconds=processing_time,
                    snapshot_id=snapshot_id,
                )
            else:
                result = Result.fail(
                    "; ".join(error_messages) or "no artifacts were produced",
                    # Distinguish reported capture errors from missing outputs.
                    "archive_generation_failed" if outcome.errors
                    else "missing_required_artifacts",
                    archive_path=output_folder,
                    artifacts_created=created,
                    failed_artifacts=failed,
                    missing_artifacts=missing,
                    skipped_generators=skipped,
                    processing_time_seconds=processing_time,
                )

            logger.info(f"🎉 Archive creation completed for request {request_id} in {processing_time:.2f}s")
            # Timing summary
            timing_parts = [f"{name}: {elapsed:.2f}s" for name, elapsed in generator_timings]
            timing_parts.append(f"metadata: {meta_elapsed:.2f}s")
            timing_parts.append(f"storage: {storage_elapsed:.2f}s")
            logger.info(f"📊 Timing breakdown: {' | '.join(timing_parts)} | total: {processing_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Archive creation failed: {e}", exc_info=True)
            return self._failure_result(
                start_time, str(e), 'processing_error'
            )
