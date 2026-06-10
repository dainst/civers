"""
Unit tests for Pydantic models.
"""

import json
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    ArchivedUrl, 
    Snapshot, 
    Artifact, 
    PaginatedResponse, 
    ErrorResponse, 
    SuccessResponse,
    PaginationMeta,
    CitationResponse
)


class TestSnapshot:
    """Test cases for Snapshot model."""
    
    def test_snapshot_creation_valid(self):
        """Test creating a valid snapshot."""
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com",
            title="Example Domain",
            metadata={"status": 200, "content_type": "text/html"},
            available_artifacts=["archive.warc", "screenshot.png"]
        )
        
        assert snapshot.snapshot_id == "20240315T143022Z"
        assert str(snapshot.url) == "https://example.com/"
        assert snapshot.title == "Example Domain"
        assert snapshot.has_warc is True
        assert snapshot.has_screenshot is True
        assert snapshot.has_singlefile is False
    
    def test_snapshot_id_validation(self):
        """Test snapshot ID validation."""
        # Valid format
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com"
        )
        assert snapshot.snapshot_id == "20240315T143022Z"
        
        # Invalid formats should raise ValidationError
        with pytest.raises(ValidationError):
            Snapshot(
                snapshot_id="invalid-format",
                timestamp="2024-03-15T14:30:22Z",
                url="https://example.com"
            )
    
    def test_timestamp_parsing(self):
        """Test timestamp parsing from various formats."""
        # ISO format
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com"
        )
        assert snapshot.timestamp == datetime(2024, 3, 15, 14, 30, 22)
        
        # Compact format
        snapshot2 = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="20240315T143022Z",
            url="https://example.com"
        )
        assert snapshot2.timestamp == datetime(2024, 3, 15, 14, 30, 22)
    
    def test_artifact_deduplication(self):
        """Test artifact deduplication."""
        # Valid artifacts with duplicates
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com",
            available_artifacts=["warc.file", "screenshot.png", "warc.file", "singlefile.html"]
        )
        # Should deduplicate
        assert len(snapshot.available_artifacts) == 3
        assert "warc.file" in snapshot.available_artifacts
        assert "screenshot.png" in snapshot.available_artifacts
        assert "singlefile.html" in snapshot.available_artifacts
        
        # Note: Artifact type validation now happens at the API/upload layer,
        # not in the model. Models just hold data.
    
    def test_metadata_validation(self):
        """Test metadata structure validation."""
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com",
            metadata={"status": "200", "content_length": "1024"}  # String values
        )
        
        # Should convert to proper types
        assert snapshot.metadata["status"] == 200
        assert snapshot.metadata["content_length"] == 1024
    
    def test_computed_properties(self):
        """Test computed properties."""
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com",
            metadata={"status": 200, "content_type": "text/html", "content_length": 1024},
            available_artifacts=["warc.file", "screenshot.png"]
        )
        
        assert snapshot.formatted_timestamp == "2024-03-15 14:30:22 UTC"
        assert snapshot.date_only == "2024-03-15"
        assert snapshot.time_only == "14:30:22"
        assert snapshot.artifact_count == 2
        assert snapshot.status_code == 200
        assert snapshot.content_type == "text/html"
        assert snapshot.content_length == 1024


class TestArtifact:
    """Test cases for Artifact model."""
    
    def test_artifact_creation(self):
        """Test creating a valid artifact."""
        artifact = Artifact(
            artifact_type="warc.file",
            filename="warc.file",
            size_bytes=1048576,
            exists=True
        )
        
        assert artifact.artifact_type == "warc.file"
        assert artifact.filename == "warc.file"
        assert artifact.size_bytes == 1048576
        assert artifact.exists is True
    
    def test_artifact_type_as_string(self):
        """Test artifact type accepts any string."""
        # Using common artifact types
        artifact = Artifact(
            artifact_type="screenshot.png",
            filename="screenshot.png"
        )
        assert artifact.artifact_type == "screenshot.png"
        
        # Any string is valid at model level
        # (validation happens at API layer using config)
        artifact2 = Artifact(
            artifact_type="custom.type",
            filename="custom.file"
        )
        assert artifact2.artifact_type == "custom.type"
    
    def test_filename_security_validation(self):
        """Test filename validation for security."""
        # Valid filename
        artifact = Artifact(
            artifact_type="warc.file",
            filename="warc.file"
        )
        assert artifact.filename == "warc.file"
        
        # Invalid filenames should raise ValidationError
        with pytest.raises(ValidationError):
            Artifact(
                artifact_type="warc.file",
                filename="../../../etc/passwd"
            )
    
    def test_formatted_size(self):
        """Test file size formatting."""
        # Bytes
        artifact = Artifact(
            artifact_type="warc.file",
            filename="warc.file",
            size_bytes=512
        )
        assert artifact.formatted_size == "512 bytes"
        
        # KB
        artifact_kb = Artifact(
            artifact_type="warc.file",
            filename="warc.file",
            size_bytes=2048
        )
        assert artifact_kb.formatted_size == "2.0 KB"
        
        # MB
        artifact_mb = Artifact(
            artifact_type="warc.file",
            filename="warc.file",
            size_bytes=1048576
        )
        assert artifact_mb.formatted_size == "1.0 MB"
    

    
    def test_properties(self):
        """Test artifact properties."""
        warc = Artifact(artifact_type="archive.warc", filename="archive.warc")
        assert warc.is_replayable is True
        assert warc.is_viewable is False
        
        screenshot = Artifact(artifact_type="screenshot.png", filename="screenshot.png")
        assert screenshot.is_viewable is True
        assert screenshot.is_replayable is False


class TestArchivedUrl:
    """Test cases for ArchivedUrl model."""
    
    def test_archived_url_creation(self):
        """Test creating a valid archived URL."""
        snapshots = [
            Snapshot(
                snapshot_id="20240315T143022Z",
                timestamp="2024-03-15T14:30:22Z",
                url="https://example.com",
                title="Example Domain"
            ),
            Snapshot(
                snapshot_id="20240316T120000Z", 
                timestamp="2024-03-16T12:00:00Z",
                url="https://example.com",
                title="Example Domain Updated"
            )
        ]
        
        archived_url = ArchivedUrl(
            url_id="example_com",
            original_url="https://example.com",
            folder_name="example_com",
            snapshots=snapshots
        )
        
        assert archived_url.url_id == "example_com"
        assert str(archived_url.original_url) == "https://example.com/"
        assert archived_url.snapshot_count == 2
    
    def test_url_id_validation(self):
        """Test URL ID validation."""
        # Valid URL ID
        archived_url = ArchivedUrl(
            url_id="example_com_path_123",
            original_url="https://example.com",
            folder_name="example_com_path_123"
        )
        assert archived_url.url_id == "example_com_path_123"
        
        # Invalid URL ID should raise ValidationError
        with pytest.raises(ValidationError):
            ArchivedUrl(
                url_id="invalid/url/id",
                original_url="https://example.com",
                folder_name="invalid"
            )
    
    def test_url_validation(self):
        """Test URL validation and normalization."""
        # URL without scheme should be normalized
        archived_url = ArchivedUrl(
            url_id="example_com",
            original_url="example.com",  # Missing https://
            folder_name="example_com"
        )
        assert str(archived_url.original_url) == "https://example.com/"
    
    def test_snapshot_sorting(self):
        """Test snapshot sorting by timestamp."""
        snapshots = [
            Snapshot(
                snapshot_id="20240315T143022Z",
                timestamp="2024-03-15T14:30:22Z",
                url="https://example.com"
            ),
            Snapshot(
                snapshot_id="20240316T120000Z",
                timestamp="2024-03-16T12:00:00Z",
                url="https://example.com"
            )
        ]
        
        archived_url = ArchivedUrl(
            url_id="example_com",
            original_url="https://example.com", 
            folder_name="example_com",
            snapshots=snapshots
        )
        
        # Should be sorted newest first
        assert archived_url.snapshots[0].snapshot_id == "20240316T120000Z"
        assert archived_url.snapshots[1].snapshot_id == "20240315T143022Z"
    
    def test_computed_properties(self):
        """Test computed properties."""
        snapshots = [
            Snapshot(
                snapshot_id="20240315T143022Z",
                timestamp="2024-03-15T14:30:22Z",
                url="https://example.com"
            ),
            Snapshot(
                snapshot_id="20240316T120000Z",
                timestamp="2024-03-16T12:00:00Z", 
                url="https://example.com"
            )
        ]
        
        archived_url = ArchivedUrl(
            url_id="example_com",
            original_url="https://example.com",
            folder_name="example_com",
            snapshots=snapshots
        )
        
        assert archived_url.snapshot_count == 2
        assert archived_url.first_captured == datetime(2024, 3, 15, 14, 30, 22)
        assert archived_url.last_captured == datetime(2024, 3, 16, 12, 0, 0)
        assert archived_url.date_range == "2024-03-15 to 2024-03-16"


class TestResponseModels:
    """Test cases for API response models."""
    
    def test_pagination_meta(self):
        """Test pagination metadata creation."""
        meta = PaginationMeta.create(page=2, limit=10, total_count=95)
        
        assert meta.page == 2
        assert meta.limit == 10
        assert meta.total_count == 95
        assert meta.total_pages == 10
        assert meta.has_next is True
        assert meta.has_previous is True
    
    def test_paginated_response(self):
        """Test paginated response creation."""
        snapshots = [
            Snapshot(
                snapshot_id="20240315T143022Z",
                timestamp="2024-03-15T14:30:22Z",
                url="https://example.com"
            )
        ]
        
        pagination = PaginationMeta.create(page=1, limit=10, total_count=1)
        response = PaginatedResponse[Snapshot](data=snapshots, pagination=pagination)
        
        assert response.success is True
        assert len(response.data) == 1
        assert response.pagination.total_count == 1
    
    def test_error_response(self):
        """Test error response creation."""
        response = ErrorResponse(
            error="Validation Error",
            message="Invalid data provided"
        )
        
        assert response.success is False
        assert response.error == "Validation Error"
        assert response.message == "Invalid data provided"
    
    def test_success_response(self):
        """Test success response creation."""
        response = SuccessResponse(
            message="Operation completed successfully",
            data={"processed": 5}
        )
        
        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.data["processed"] == 5
    
    def test_citation_response(self):
        """Test citation response creation."""
        response = CitationResponse(
            snapshot_id="20240315T143022Z",
            style="APA",
            citation="Example Domain. (2024, March 15). Retrieved March 20, 2024, from https://example.com",
            url="https://example.com",
            title="Example Domain",
            timestamp="2024-03-15T14:30:22Z",
            access_date="2024-03-20T10:15:30Z"
        )
        
        assert response.success is True
        assert response.style == "APA"
        assert "Example Domain" in response.citation


class TestModelSerialization:
    """Test JSON serialization and deserialization."""
    
    def test_snapshot_json_serialization(self):
        """Test snapshot JSON serialization."""
        snapshot = Snapshot(
            snapshot_id="20240315T143022Z",
            timestamp="2024-03-15T14:30:22Z",
            url="https://example.com",
            title="Example Domain",
            available_artifacts=["warc.file"]
        )
        
        # Test serialization
        json_data = snapshot.model_dump()
        assert json_data["snapshot_id"] == "20240315T143022Z"
        assert str(json_data["url"]) == "https://example.com/"
        
        # Test JSON string
        json_str = snapshot.model_dump_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Example Domain"
    
    def test_archived_url_json_serialization(self):
        """Test archived URL JSON serialization."""
        archived_url = ArchivedUrl(
            url_id="example_com",
            original_url="https://example.com",
            folder_name="example_com"
        )
        
        json_data = archived_url.model_dump()
        assert json_data["url_id"] == "example_com"
        assert str(json_data["original_url"]) == "https://example.com/"
    
    def test_model_deserialization(self):
        """Test model creation from dictionary."""
        data = {
            "snapshot_id": "20240315T143022Z",
            "timestamp": "2024-03-15T14:30:22Z",
            "url": "https://example.com",
            "title": "Example Domain",
            "metadata": {"status": 200},
            "available_artifacts": ["warc.file"]
        }
        
        snapshot = Snapshot(**data)
        assert snapshot.snapshot_id == "20240315T143022Z"
        assert snapshot.title == "Example Domain"


if __name__ == "__main__":
    pytest.main([__file__])