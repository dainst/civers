"""
Unit tests for security utilities.

Tests the security validation functions and path protection utilities.
"""

import pytest
import tempfile
from pathlib import Path

from app.utils import (
    validate_snapshot_id,
    validate_artifact_type,
    get_content_type,
    get_content_disposition,
    validate_file_path,
    sanitize_filename,
    validate_request_parameters,
    SecurityValidationError
)
from configs.models import ValidationConfig


@pytest.fixture
def validation_config():
    """Fixture providing default validation configuration."""
    return ValidationConfig()


class TestSnapshotIdValidation:
    """Test cases for snapshot ID validation."""
    
    def test_valid_snapshot_id_new_format(self, validation_config):
        """Test validation of valid request-based snapshot IDs."""
        valid_ids = [
            "req_test-request-1_20250904_061411",
            "req_archive-job-123_20241201_143022",
            "req_simple_20230101_000000"
        ]
        
        for snapshot_id in valid_ids:
            result = validate_snapshot_id(snapshot_id, validation_config)
            assert result == snapshot_id
    
    
    def test_empty_snapshot_id(self, validation_config):
        """Test that empty snapshot ID raises error."""
        with pytest.raises(SecurityValidationError, match="cannot be empty"):
            validate_snapshot_id("", validation_config)
    
    def test_long_snapshot_id(self, validation_config):
        """Test that overly long snapshot ID raises error."""
        long_id = "req_" + "x" * 100
        with pytest.raises(SecurityValidationError, match="too long"):
            validate_snapshot_id(long_id, validation_config)
    
    def test_path_traversal_attempts(self, validation_config):
        """Test that path traversal attempts are blocked."""
        malicious_ids = [
            "req_test_20250904_061411/../../../etc/passwd",
            "../req_test_20250904_061411",
            "req_test/../../secret",
            "req_test\\..\\..\\windows\\system32"
        ]
        
        for snapshot_id in malicious_ids:
            with pytest.raises(SecurityValidationError, match="Invalid characters"):
                validate_snapshot_id(snapshot_id, validation_config)
    
    def test_dangerous_characters(self, validation_config):
        """Test that dangerous characters are rejected."""
        dangerous_ids = [
            "req_test\0_20250904_061411",  # Null byte
            "req_test\x01_20250904_061411",  # Control character
            "req_test\x1f_20250904_061411"   # Another control character
        ]
        
        for snapshot_id in dangerous_ids:
            with pytest.raises(SecurityValidationError, match="Invalid characters"):
                validate_snapshot_id(snapshot_id, validation_config)
    
    def test_invalid_format(self, validation_config):
        """Test that improperly formatted IDs are rejected."""
        invalid_ids = [
            "not_a_valid_format",
            "req_test",  # Missing timestamp
            "20240315T14302Z",  # Wrong legacy format
            "req__20250904_061411",  # Empty request ID
            "req_test_20250904"  # Missing time
        ]
        
        for snapshot_id in invalid_ids:
            with pytest.raises(SecurityValidationError, match="format invalid"):
                validate_snapshot_id(snapshot_id, validation_config)


class TestArtifactTypeValidation:
    """Test cases for artifact type validation."""
    
    def test_valid_artifact_types(self, validation_config):
        """Test validation of all allowed artifact types."""
        for artifact_type in validation_config.allowed_artifact_types:
            result = validate_artifact_type(artifact_type, validation_config)
            assert result == artifact_type
    
    def test_empty_artifact_type(self, validation_config):
        """Test that empty artifact type raises error."""
        with pytest.raises(SecurityValidationError, match="cannot be empty"):
            validate_artifact_type("", validation_config)
    
    def test_path_traversal_in_artifact_type(self, validation_config):
        """Test that path traversal in artifact type is blocked."""
        malicious_types = [
            "../../etc/passwd",
            "../secret.txt",
            "archive.wacz/../../../etc/passwd",
            "..\\..\\windows\\system32\\config"
        ]
        
        for artifact_type in malicious_types:
            with pytest.raises(SecurityValidationError, match="Invalid characters"):
                validate_artifact_type(artifact_type, validation_config)
    
    def test_disallowed_artifact_type(self, validation_config):
        """Test that disallowed artifact types are rejected."""
        disallowed_types = [
            "malicious.exe",
            "secret.txt",
            "config.ini",
            "password.log"
        ]
        
        for artifact_type in disallowed_types:
            with pytest.raises(SecurityValidationError, match="not allowed"):
                validate_artifact_type(artifact_type, validation_config)


class TestContentTypeMapping:
    """Test cases for content type mapping."""
    
    def test_all_artifact_types_have_content_type(self, validation_config):
        """Test that all allowed artifact types have content type mappings."""
        for artifact_type in validation_config.allowed_artifact_types:
            content_type = get_content_type(artifact_type, validation_config)
            assert content_type is not None
            assert content_type != ""
            assert content_type in validation_config.content_type_mappings.values()
    
    def test_specific_content_types(self, validation_config):
        """Test specific content type mappings."""
        expected_mappings = {
            "archive.wacz": "application/zip",
            "metadata.json": "application/json",
            "screenshot.png": "image/png",
            "singlefile.html": "text/html",
            "archive.warc": "application/warc",
            "document.html": "text/html"
        }
        
        for artifact_type, expected_type in expected_mappings.items():
            assert get_content_type(artifact_type, validation_config) == expected_type
    
    def test_unknown_artifact_type_fallback(self, validation_config):
        """Test fallback content type for unknown artifact types."""
        unknown_type = "unknown.xyz"
        assert get_content_type(unknown_type, validation_config) == "application/octet-stream"


class TestContentDisposition:
    """Test cases for content disposition header generation."""
    
    def test_content_disposition_format(self, validation_config):
        """Test that content disposition headers are properly formatted."""
        snapshot_id = "req_test_20250904_061411"
        artifact_type = "archive.wacz"
        
        disposition = get_content_disposition(artifact_type, snapshot_id)
        
        assert disposition.startswith('attachment; filename="')
        assert disposition.endswith('"')
        assert snapshot_id in disposition
        assert artifact_type in disposition
    
    def test_content_disposition_sanitization(self, validation_config):
        """Test that dangerous characters in filenames are sanitized."""
        snapshot_id = "req_test/../dangerous_20250904_061411"
        artifact_type = "screenshot.png"
        
        disposition = get_content_disposition(artifact_type, snapshot_id)
        
        # Should not contain path traversal characters
        assert "../" not in disposition
        assert "\\" not in disposition


class TestFilePathValidation:
    """Test cases for file path security validation."""
    
    def test_valid_path_within_storage(self, validation_config):
        """Test that valid paths within storage directory are accepted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_root = Path(temp_dir)
            valid_file = storage_root / "test_domain" / "test_path" / "req_test_20250904_061411" / "archive.wacz"
            
            # Create the directory structure
            valid_file.parent.mkdir(parents=True, exist_ok=True)
            valid_file.write_text("test content")
            
            result = validate_file_path(valid_file, storage_root)
            assert result == valid_file.resolve()
    
    def test_path_traversal_blocked(self, validation_config):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_root = Path(temp_dir)
            
            # Try to access file outside storage directory
            malicious_path = storage_root / ".." / "etc" / "passwd"
            
            with pytest.raises(SecurityValidationError, match="outside allowed storage"):
                validate_file_path(malicious_path, storage_root)
    
    def test_symlink_traversal_blocked(self, validation_config):
        """Test that symlink-based path traversal is blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_root = Path(temp_dir)
            
            # Create a symlink that points outside the storage directory
            external_dir = Path(temp_dir).parent / "external"
            external_dir.mkdir(exist_ok=True)
            external_file = external_dir / "secret.txt"
            external_file.write_text("secret content")
            
            symlink_path = storage_root / "symlink"
            symlink_path.symlink_to(external_file)
            
            with pytest.raises(SecurityValidationError, match="outside allowed storage"):
                validate_file_path(symlink_path, storage_root)


class TestFilenameSanitization:
    """Test cases for filename sanitization."""
    
    def test_safe_filename_unchanged(self, validation_config):
        """Test that safe filenames are unchanged."""
        safe_names = [
            "archive.wacz",
            "metadata.json",
            "test-file_123.png"
        ]
        
        for filename in safe_names:
            result = sanitize_filename(filename, validation_config)
            assert result == filename
    
    def test_dangerous_characters_replaced(self, validation_config):
        """Test that dangerous characters are replaced."""
        dangerous_names = [
            "file/with/slashes.txt",
            "file\\with\\backslashes.txt", 
            "file<with>brackets.txt",
            "file|with|pipes.txt"
        ]
        
        for filename in dangerous_names:
            result = sanitize_filename(filename, validation_config)
            assert "/" not in result
            assert "\\" not in result
            assert "<" not in result
            assert ">" not in result
            assert "|" not in result
    
    def test_empty_filename_handling(self, validation_config):
        """Test handling of empty or whitespace-only filenames."""
        empty_names = ["", "   ", "...", "   .   "]
        
        for filename in empty_names:
            result = sanitize_filename(filename, validation_config)
            assert result == "unnamed_file"
    
    def test_long_filename_truncation(self, validation_config):
        """Test that overly long filenames are truncated."""
        long_name = "x" * 300 + ".txt"
        result = sanitize_filename(long_name, validation_config)
        
        assert len(result) <= 255
        assert result.endswith(".txt")  # Extension should be preserved


class TestRequestParameterValidation:
    """Test cases for combined request parameter validation."""
    
    def test_valid_parameters(self, validation_config):
        """Test validation of valid parameter combinations."""
        valid_combinations = [
            ("req_test_20250904_061411", "archive.wacz"),
            ("req_archive-123_20241201_143022", "screenshot.png"),
            ("req_test_20240315_143022", "metadata.json")
        ]
        
        for snapshot_id, artifact_type in valid_combinations:
            result_id, result_type = validate_request_parameters(snapshot_id, artifact_type, validation_config)
            assert result_id == snapshot_id
            assert result_type == artifact_type
    
    def test_invalid_snapshot_id_in_combination(self, validation_config):
        """Test that invalid snapshot ID fails validation even with valid artifact type."""
        with pytest.raises(SecurityValidationError):
            validate_request_parameters("../../../etc/passwd", "archive.wacz", validation_config)
    
    def test_invalid_artifact_type_in_combination(self, validation_config):
        """Test that invalid artifact type fails validation even with valid snapshot ID."""
        with pytest.raises(SecurityValidationError):
            validate_request_parameters("req_test_20250904_061411", "malicious.exe", validation_config)