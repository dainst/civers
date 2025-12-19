"""
File storage utilities for structured archive storage.

These utilities are used by both FilesystemStorageProvider and
SQLiteStorageProvider to ensure consistent file storage behavior.
All file operations are atomic and include proper error handling.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, IO, List
from ..config.models import ValidationConfig
from ..custom_exceptions.exceptions.api_exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_artifact_type(
    artifact_type: str,
    validation_config: ValidationConfig
) -> None:
    """
    Validate artifact type against allowed types.

    Args:
        artifact_type: Artifact filename (e.g., 'archive.wacz')
        validation_config: Validation configuration

    Raises:
        ValidationError: If artifact type not allowed

    Examples:
        >>> config = ValidationConfig()
        >>> validate_artifact_type('archive.wacz', config)  # OK
        >>> validate_artifact_type('malware.exe', config)  # Raises ValidationError
    """
    if artifact_type not in validation_config.allowed_artifact_types:
        raise ValidationError(
            f"Invalid artifact type: {artifact_type}. "
            f"Allowed types: {sorted(validation_config.allowed_artifact_types)}"
        )


def create_storage_directory(storage_path: Path, allow_existing: bool = False) -> bool:
    """
    Create storage directory.

    Creates the directory and all necessary parents. By default, fails if the
    directory already exists to prevent overwriting. Can be configured to allow
    existing directories for idempotent operations.

    Args:
        storage_path: Path to create
        allow_existing: If True, allow existing directory (for adding files to existing snapshot)

    Returns:
        True if directory was created, False if it already existed (when allow_existing=True)

    Raises:
        ValidationError: If directory already exists and allow_existing=False
        StorageError: If directory creation fails for other reasons

    Examples:
        >>> from pathlib import Path
        >>> create_storage_directory(Path('/tmp/test_snapshot'))  # Creates directory, returns True
        >>> create_storage_directory(Path('/tmp/test_snapshot'))  # Raises ValidationError
        >>> create_storage_directory(Path('/tmp/test_snapshot'), allow_existing=True)  # Returns False
    """
    from ..storage.providers.storage_provider_interface import StorageError

    try:
        if storage_path.exists():
            if not allow_existing:
                raise ValidationError(
                    f"Snapshot already exists: {storage_path.name}. "
                    "Use a different request_id or timestamp, or set allow_existing=True."
                )
            logger.debug(f"Directory already exists: {storage_path}")
            return False

        storage_path.mkdir(parents=True, exist_ok=False)
        logger.info(f"Created directory: {storage_path}")
        return True

    except ValidationError:
        # Re-raise ValidationError as-is (don't wrap it)
        raise
    except FileExistsError:
        # This can happen in race conditions
        if allow_existing:
            logger.debug(f"Directory created by another process: {storage_path}")
            return False
        raise ValidationError(f"Snapshot already exists: {storage_path.name}")
    except PermissionError as e:
        logger.error(f"Permission denied creating directory {storage_path}: {e}")
        raise StorageError(f"Permission denied: {str(e)}") from e
    except Exception as e:
        logger.error(f"Failed to create directory {storage_path}: {e}")
        raise StorageError(f"Directory creation failed: {str(e)}") from e


def write_file_atomic(
    file_path: Path,
    file_stream: IO,
    validation_config: ValidationConfig,
    skip_if_exists: bool = False
) -> bool:
    """
    Write file atomically using temp file + rename.

    This ensures that if the write fails partway through, we don't end up
    with a corrupted file. The file is first written to a temporary location,
    then atomically renamed to the final destination.

    Args:
        file_path: Destination file path
        file_stream: File content stream
        validation_config: Validation configuration
        skip_if_exists: If True, skip writing if file already exists (for idempotent operations)

    Returns:
        True if file was written, False if it already existed (when skip_if_exists=True)

    Raises:
        ValidationError: If artifact type invalid
        StorageError: If file write fails

    Examples:
        >>> from io import BytesIO
        >>> from pathlib import Path
        >>> content = BytesIO(b'file content')
        >>> write_file_atomic(Path('/tmp/test.wacz'), content, config)  # Returns True
        >>> write_file_atomic(Path('/tmp/test.wacz'), content, config, skip_if_exists=True)  # Returns False
    """
    from ..storage.providers.storage_provider_interface import StorageError

    # Validate artifact type
    validate_artifact_type(file_path.name, validation_config)

    # Check if file exists and should be skipped
    if skip_if_exists and file_path.exists():
        logger.debug(f"File already exists, skipping: {file_path.name}")
        return False

    temp_path = file_path.with_suffix(file_path.suffix + '.tmp')

    try:
        # Write to temp file
        with open(temp_path, 'wb') as f:
            shutil.copyfileobj(file_stream, f)

        # Atomic rename
        temp_path.rename(file_path)

        # Log success with file size
        file_size = file_path.stat().st_size
        logger.debug(f"Wrote file: {file_path.name} ({file_size} bytes)")
        return True

    except PermissionError as e:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"Permission denied writing file {file_path}: {e}")
        raise StorageError(f"Permission denied: {str(e)}") from e
    except Exception as e:
        # Cleanup temp file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")

        logger.error(f"Failed to write file {file_path}: {e}")
        raise StorageError(f"File write failed: {str(e)}") from e


def cleanup_directory(storage_path: Path) -> None:
    """
    Clean up directory (used on failure).

    Removes the directory and all its contents. Used to clean up after
    failed snapshot creation. Logs warnings if cleanup fails but doesn't
    raise exceptions.

    Args:
        storage_path: Directory to remove

    Examples:
        >>> from pathlib import Path
        >>> cleanup_directory(Path('/tmp/failed_snapshot'))
    """
    try:
        if storage_path.exists() and storage_path.is_dir():
            shutil.rmtree(storage_path)
            logger.debug(f"Cleaned up directory: {storage_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup directory {storage_path}: {e}")


def store_snapshot_files(
    storage_path: Path,
    files: Dict[str, IO],
    validation_config: ValidationConfig,
    allow_existing: bool = False
) -> List[str]:
    """
    Store all snapshot files in structured directory.

    This is the main shared utility used by both storage providers.
    It creates the directory and writes all artifact files atomically.
    If any step fails, it cleans up the partially created directory.

    Supports idempotent operations: when allow_existing=True, it will add
    new files to an existing snapshot without overwriting existing files.

    Note: metadata.json should be included in the files dict as a regular file.

    Args:
        storage_path: Full path to snapshot directory
        files: Dictionary of artifact_type → file_stream (including metadata.json)
        validation_config: Validation configuration
        allow_existing: If True, allow adding files to existing snapshot (idempotent)

    Returns:
        List of artifact filenames written
        Note: If allow_existing=True, only newly written files are included

    Raises:
        ValidationError: If validation fails (invalid artifact type, directory exists when allow_existing=False)
        StorageError: If storage operation fails

    Examples:
        >>> from pathlib import Path
        >>> from io import BytesIO
        >>> files = {
        ...     'archive.wacz': BytesIO(b'wacz content'),
        ...     'screenshot.png': BytesIO(b'png content'),
        ...     'metadata.json': BytesIO(b'{"url": "https://example.com"}')
        ... }
        >>> # First upload - creates snapshot
        >>> artifacts = store_snapshot_files(
        ...     Path('/tmp/snapshot'),
        ...     files,
        ...     ValidationConfig()
        ... )
        >>> print(artifacts)
        ['archive.wacz', 'screenshot.png', 'metadata.json']
        >>>
        >>> # Second upload - adds new file to existing snapshot
        >>> new_files = {'singlefile.html': BytesIO(b'html content')}
        >>> artifacts = store_snapshot_files(
        ...     Path('/tmp/snapshot'),
        ...     new_files,
        ...     ValidationConfig(),
        ...     allow_existing=True
        ... )
        >>> print(artifacts)
        ['singlefile.html']  # Only new files
    """
    directory_created = False
    try:
        # Create directory (or allow existing)
        directory_created = create_storage_directory(storage_path, allow_existing=allow_existing)

        # Write artifact files
        uploaded_artifacts = []
        for artifact_type, file_stream in files.items():
            file_path = storage_path / artifact_type
            # Skip existing files when allow_existing=True
            was_written = write_file_atomic(
                file_path,
                file_stream,
                validation_config,
                skip_if_exists=allow_existing
            )
            if was_written:
                uploaded_artifacts.append(artifact_type)

        if directory_created:
            logger.info(
                f"Created snapshot with {len(uploaded_artifacts)} files in {storage_path} "
                f"(artifacts: {', '.join(uploaded_artifacts)})"
            )
        else:
            logger.info(
                f"Added {len(uploaded_artifacts)} files to existing snapshot {storage_path} "
                f"(new artifacts: {', '.join(uploaded_artifacts)})"
            )
        return uploaded_artifacts

    except Exception as e:
        # Only cleanup if WE created the directory (don't delete existing snapshots!)
        if directory_created:
            cleanup_directory(storage_path)
            logger.error(f"Failed to store snapshot files, cleaned up: {e}")
        else:
            logger.error(f"Failed to add files to existing snapshot: {e}")
        raise
