"""
Unit tests for the new storage architecture with providers and service.
"""

import json
import tempfile
import pytest
from pathlib import Path
from app.storage import FilesystemStorageProvider, StorageService, create_storage_provider, create_storage_service
from configs import StorageConfig, FilesystemConfig, CacheConfig, AppConfig
from configs.models import ValidationConfig
from app.models import Snapshot, ArchivedUrl


class TestFilesystemStorageProvider:
    """Test cases for FilesystemStorageProvider."""
    
    @pytest.fixture
    def temp_archives(self):
        """Create temporary archives directory with test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archives_path = Path(temp_dir) / "archives"
            archives_path.mkdir()
            
            # Create test structure: archives/domain/path/req_id_timestamp/
            domain_dir = archives_path / "example_com"
            domain_dir.mkdir()
            
            path_dir = domain_dir / "home_page"
            path_dir.mkdir()
            
            request_dir = path_dir / "req_test-1_20250904_120000"
            request_dir.mkdir()
            
            # Create metadata.json
            metadata = {
                "archive_info": {
                    "url": "https://example.com",
                    "request_id": "test-1"
                },
                "title": "Example Domain"
            }
            with open(request_dir / "metadata.json", "w") as f:
                json.dump(metadata, f)
            
            # Create artifacts
            (request_dir / "archive.wacz").write_bytes(b"fake wacz data")
            (request_dir / "screenshot.png").write_bytes(b"fake image data")
            
            yield archives_path

    def test_provider_initialization(self, temp_archives):
        """Test provider initialization."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        assert provider.storage_path == temp_archives
        assert provider.timeout_seconds == 10

    def test_get_all_urls(self, temp_archives):
        """Test getting all URLs from storage."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        urls = provider.get_all_urls()
        
        assert len(urls) == 1
        assert "example_com_home_page" in urls
        
        archived_url = urls["example_com_home_page"]
        assert isinstance(archived_url, ArchivedUrl)
        assert archived_url.url_id == "example_com_home_page"
        assert str(archived_url.original_url) == "https://example.com/"
        assert len(archived_url.snapshots) == 1

    def test_get_url_by_id(self, temp_archives):
        """Test getting specific URL by ID."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        
        # Test existing URL
        archived_url = provider.get_url_by_id("example_com_home_page")
        assert archived_url is not None
        assert archived_url.url_id == "example_com_home_page"
        
        # Test non-existent URL
        missing_url = provider.get_url_by_id("nonexistent_url")
        assert missing_url is None

    def test_get_snapshot_by_id(self, temp_archives):
        """Test getting specific snapshot by ID."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        
        # Test existing snapshot
        snapshot = provider.get_snapshot_by_id("req_test-1_20250904_120000")
        assert snapshot is not None
        assert isinstance(snapshot, Snapshot)
        assert snapshot.snapshot_id == "req_test-1_20250904_120000"
        assert str(snapshot.url) == "https://example.com/"
        
        # Test non-existent snapshot
        missing_snapshot = provider.get_snapshot_by_id("nonexistent_snapshot")
        assert missing_snapshot is None

    def test_artifact_operations(self, temp_archives):
        """Test artifact-related operations."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        snapshot_id = "req_test-1_20250904_120000"
        
        # Test artifact exists
        assert provider.artifact_exists(snapshot_id, "archive.wacz")
        assert provider.artifact_exists(snapshot_id, "screenshot.png")
        assert not provider.artifact_exists(snapshot_id, "nonexistent.file")
        
        # Test get artifact path
        wacz_path = provider.get_artifact_path(snapshot_id, "archive.wacz")
        assert wacz_path is not None
        assert wacz_path.exists()
        assert wacz_path.name == "archive.wacz"
        
        # Test get artifact stream
        with provider.get_artifact_stream(snapshot_id, "archive.wacz") as stream:
            assert stream is not None
            data = stream.read()
            assert data == b"fake wacz data"

    def test_snapshot_pydantic_model(self, temp_archives):
        """Test that snapshots are properly created as Pydantic models."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        snapshot = provider.get_snapshot_by_id("req_test-1_20250904_120000")
        
        assert isinstance(snapshot, Snapshot)
        assert isinstance(snapshot.folder_path, str)  # Should be string for Pydantic
        assert snapshot.title == "Example Domain"
        assert "archive.wacz" in snapshot.available_artifacts
        assert "screenshot.png" in snapshot.available_artifacts
        

class TestStorageService:
    """Test cases for StorageService layer."""
    
    @pytest.fixture
    def temp_archives(self):
        """Create temporary archives directory with test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archives_path = Path(temp_dir) / "archives"
            archives_path.mkdir()
            
            # Create multiple domains and URLs for testing
            for domain in ["example_com", "test_org"]:
                domain_dir = archives_path / domain
                domain_dir.mkdir()
                
                path_dir = domain_dir / "home_page"
                path_dir.mkdir()
                
                request_dir = path_dir / f"req_{domain}_20250904_120000"
                request_dir.mkdir()
                
                metadata = {
                    "archive_info": {
                        "url": f"https://{domain.replace('_', '.')}",
                        "request_id": domain
                    }
                }
                with open(request_dir / "metadata.json", "w") as f:
                    json.dump(metadata, f)
            
            yield archives_path

    def test_service_initialization(self, temp_archives):
        """Test service initialization with provider."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        service = StorageService(provider, cache_ttl_seconds=30)
        
        assert service.provider == provider
        assert service.cache_ttl_seconds == 30

    def test_service_caching(self, temp_archives):
        """Test service caching functionality."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        service = StorageService(provider, cache_ttl_seconds=60)
        
        # First call should populate cache
        urls1 = service.get_all_urls()
        assert len(urls1) == 2
        
        # Second call should use cache
        urls2 = service.get_all_urls()
        assert urls1 == urls2
        
        # Check cache stats
        stats = service.get_cache_stats()
        assert stats["cached_urls_count"] == 2
        assert stats["ttl_seconds"] == 60

    def test_service_cache_disabled(self, temp_archives):
        """Test service with caching disabled."""
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        service = StorageService(provider, cache_ttl_seconds=0)
        
        urls = service.get_all_urls()
        assert len(urls) == 2
        
        stats = service.get_cache_stats()
        assert stats["cache_disabled"] is True

    def test_find_url_by_original_url_no_partial_match(self, temp_archives):
        """Test that find_url_by_original_url does not match substrings.
        
        Fix 1: https://example.com should NOT match https://example.com/page.
        Trailing slash differences should still match.
        """
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        service = StorageService(provider, cache_ttl_seconds=60)
        
        # Exact match (with trailing slash normalization) should work
        found = service.find_url_by_original_url("https://example.com")
        assert found is not None
        
        found_with_slash = service.find_url_by_original_url("https://example.com/")
        assert found_with_slash is not None
        
        # Partial/substring match should NOT work
        longer_url = service.find_url_by_original_url("https://example.com/page/subpage")
        assert longer_url is None
        
        # Completely different URL should not match
        different = service.find_url_by_original_url("https://other-site.org")
        assert different is None

    def test_service_thread_safety(self, temp_archives):
        """Test that concurrent cache access doesn't raise exceptions.
        
        Fix 5: Multiple threads accessing get_all_urls concurrently
        should not corrupt cache state.
        """
        import threading
        
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        service = StorageService(provider, cache_ttl_seconds=60)
        
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    urls = service.get_all_urls()
                    assert len(urls) == 2
                    service.clear_cache()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_parse_timestamp_with_underscore_request_id(self, temp_archives):
        """Test timestamp parsing handles request IDs containing underscores.
        
        Fix 7: Folder names like req_my_complex_id_20250101_120000
        should correctly extract 20250101_120000 as the timestamp.
        """
        provider = FilesystemStorageProvider(temp_archives, ValidationConfig())
        
        # Simple request ID
        ts1 = provider._parse_timestamp("req_test-1_20250904_120000")
        assert ts1 is not None
        assert ts1.year == 2025
        assert ts1.month == 9
        assert ts1.day == 4
        assert ts1.hour == 12
        
        # Complex request ID with underscores
        ts2 = provider._parse_timestamp("req_my_complex_id_20250101_120000")
        assert ts2 is not None
        assert ts2.year == 2025
        assert ts2.month == 1
        assert ts2.day == 1
        
        # UUID-style request ID with underscores
        ts3 = provider._parse_timestamp("req_a1b2_c3d4_e5f6_20231225_235959")
        assert ts3 is not None
        assert ts3.year == 2023
        assert ts3.month == 12
        assert ts3.day == 25


class TestStorageFactory:
    """Test cases for storage factory functions."""
    
    def test_create_filesystem_provider(self):
        """Test creating filesystem provider via factory."""
        config = AppConfig(storage=StorageConfig(
            type="filesystem",
            filesystem=FilesystemConfig(
                path="/tmp/test",
                timeout_seconds=15
            )
        ))

        provider = create_storage_provider(config)
        assert isinstance(provider, FilesystemStorageProvider)
        assert str(provider.storage_path).endswith("test")
        assert provider.timeout_seconds == 15

    def test_create_storage_service(self):
        """Test creating storage service via factory."""
        config = AppConfig(storage=StorageConfig(
            type="filesystem",
            filesystem=FilesystemConfig(path="/tmp/test"),
            cache=CacheConfig(ttl_seconds=120)
        ))
        
        service = create_storage_service(config)
        assert isinstance(service, StorageService)
        assert service.cache_ttl_seconds == 120
        assert isinstance(service.provider, FilesystemStorageProvider)