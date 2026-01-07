"""
Security utilities for input validation and path protection.

This module provides security functions to prevent path traversal attacks,
validate input parameters, and ensure safe file operations.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Set

from configs.models import ValidationConfig

logger = logging.getLogger(__name__)



class SecurityValidationError(Exception):
    """Raised when security validation fails."""
    pass


def validate_snapshot_id(snapshot_id: str, validation_config: ValidationConfig) -> str:
    """
    Validate snapshot ID format and prevent malicious input.
    
    Args:
        snapshot_id: The snapshot identifier to validate
        validation_config: Validation configuration containing patterns and limits
        
    Returns:
        The validated snapshot ID
        
    Raises:
        SecurityValidationError: If snapshot ID is invalid or potentially malicious
    """
    if not snapshot_id:
        raise SecurityValidationError("Snapshot ID cannot be empty")
    
    # Check length to prevent extremely long inputs
    max_length = validation_config.snapshot_id_max_length
    if len(snapshot_id) > max_length:
        raise SecurityValidationError(f"Snapshot ID too long (max {max_length} characters)")
    
    # Check for path traversal attempts
    if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
        logger.warning(f"Path traversal attempt detected in snapshot_id: {snapshot_id}")
        raise SecurityValidationError("Invalid characters in snapshot ID")
    
    # Check for null bytes and other dangerous characters
    if "\0" in snapshot_id or any(ord(c) < 32 for c in snapshot_id if c not in ['\t']):
        logger.warning(f"Dangerous characters detected in snapshot_id: {snapshot_id}")
        raise SecurityValidationError("Invalid characters in snapshot ID")
    
    # Validate format matches expected pattern
    pattern = re.compile(validation_config.snapshot_id_pattern)
    if not pattern.match(snapshot_id):
        raise SecurityValidationError("Snapshot ID format invalid (expected: req_{id}_{timestamp})")
    
    return snapshot_id


def validate_artifact_type(artifact_type: str, validation_config: ValidationConfig) -> str:
    """
    Validate artifact type against whitelist.
    
    Args:
        artifact_type: The artifact type to validate
        validation_config: Validation configuration containing allowed types
        
    Returns:
        The validated artifact type
        
    Raises:
        SecurityValidationError: If artifact type is not allowed
    """
    if not artifact_type:
        raise SecurityValidationError("Artifact type cannot be empty")
    
    # Check for path traversal attempts
    if ".." in artifact_type or "/" in artifact_type or "\\" in artifact_type:
        logger.warning(f"Path traversal attempt detected in artifact_type: {artifact_type}")
        raise SecurityValidationError("Invalid characters in artifact type")
    
    # Check against whitelist
    allowed_types = validation_config.allowed_artifact_types
    if artifact_type not in allowed_types:
        raise SecurityValidationError(
            f"Artifact type '{artifact_type}' not allowed. "
            f"Allowed types: {', '.join(sorted(allowed_types))}"
        )
    
    return artifact_type


def get_content_type(artifact_type: str, validation_config: ValidationConfig) -> str:
    """
    Get the appropriate Content-Type header for an artifact type.
    
    Args:
        artifact_type: The artifact type (must be pre-validated)
        validation_config: Validation configuration containing content type mappings
        
    Returns:
        The Content-Type string for the artifact
    """
    return validation_config.content_type_mappings.get(artifact_type, "application/octet-stream")


def get_content_disposition(artifact_type: str, snapshot_id: str) -> str:
    """
    Generate Content-Disposition header for file downloads.

    For SingleFile HTML, use 'inline' to allow iframe display.
    For all other artifacts, use 'attachment' to force download.

    Args:
        artifact_type: The artifact type (must be pre-validated)
        snapshot_id: The snapshot identifier (must be pre-validated)

    Returns:
        The Content-Disposition header value
    """
    # Create a safe filename
    safe_filename = f"{snapshot_id}_{artifact_type}"

    # Remove any potentially dangerous characters just in case
    safe_filename = re.sub(r'[^\w\-_\.]', '_', safe_filename)

    # For SingleFile HTML, use inline to allow iframe display
    if artifact_type == 'singlefile.html':
        return f'inline; filename="{safe_filename}"'

    # For all other artifacts, force download
    return f'attachment; filename="{safe_filename}"'


def validate_file_path(file_path: Path, storage_root: Path) -> Path:
    """
    Validate that a file path is within the allowed storage directory.
    
    Args:
        file_path: The file path to validate
        storage_root: The root storage directory that files must be within
        
    Returns:
        The resolved and validated file path
        
    Raises:
        SecurityValidationError: If path is outside storage directory or invalid
    """
    try:
        # Resolve both paths to handle symlinks and relative components
        resolved_file_path = file_path.resolve()
        resolved_storage_root = storage_root.resolve()
        
        # Check that the file path is within the storage root
        if not str(resolved_file_path).startswith(str(resolved_storage_root)):
            logger.warning(f"Path traversal attempt: {file_path} outside {storage_root}")
            raise SecurityValidationError("File path outside allowed storage directory")
        
        return resolved_file_path
        
    except (OSError, RuntimeError) as e:
        logger.warning(f"Path resolution failed for {file_path}: {e}")
        raise SecurityValidationError("Invalid file path") from e


def sanitize_filename(filename: str, validation_config: ValidationConfig) -> str:
    """
    Sanitize a filename by removing dangerous characters.
    
    Args:
        filename: The filename to sanitize
        validation_config: Validation configuration containing filename limits
        
    Returns:
        A sanitized filename safe for file operations
    """
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Handle edge cases where sanitization results in only underscores or empty string
    if not sanitized or sanitized.replace('_', '').replace('.', '') == '':
        sanitized = "unnamed_file"
    
    # Limit length using configured maximum
    max_length = validation_config.filename_max_length
    if len(sanitized) > max_length:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        max_name_length = max_length - len(ext) - 1  # -1 for the dot
        sanitized = name[:max_name_length] + ('.' + ext if ext else '')
    
    return sanitized


def validate_request_parameters(snapshot_id: str, artifact_type: str, validation_config: ValidationConfig) -> tuple[str, str]:
    """
    Validate both snapshot_id and artifact_type parameters together.
    
    Args:
        snapshot_id: The snapshot identifier
        artifact_type: The artifact type
        validation_config: Validation configuration
        
    Returns:
        Tuple of (validated_snapshot_id, validated_artifact_type)
        
    Raises:
        SecurityValidationError: If either parameter is invalid
    """
    validated_snapshot_id = validate_snapshot_id(snapshot_id, validation_config)
    validated_artifact_type = validate_artifact_type(artifact_type, validation_config)
    
    return validated_snapshot_id, validated_artifact_type


def log_access_attempt(snapshot_id: str, artifact_type: str,
                      client_ip: Optional[str] = None,
                      success: bool = True,
                      failure_reason: Optional[str] = None) -> None:
    """
    Log artifact access attempts for security monitoring.

    Args:
        snapshot_id: The requested snapshot ID
        artifact_type: The requested artifact type
        client_ip: Client IP address if available
        success: Whether the access attempt was successful
        failure_reason: Specific reason for failure (e.g., 'snapshot not found', 'file not found', 'access denied')
    """
    client_info = f" from {client_ip}" if client_ip else ""

    if success:
        logger.debug(f"Artifact access SUCCESS: {snapshot_id}/{artifact_type}{client_info}")
    else:
        reason = f" ({failure_reason})" if failure_reason else ""
        logger.debug(f"Artifact access FAILED{reason}: {snapshot_id}/{artifact_type}{client_info}")
        logger.warning(f"Failed artifact access attempt{reason}: {snapshot_id}/{artifact_type}{client_info}")