"""
Tests for URL parser utilities.

Tests URL parsing, normalization, and path building functionality.
"""

import pytest
from datetime import datetime
from app.utils.url_parser import (
    normalize_domain,
    normalize_path,
    parse_url,
    generate_request_id,
    build_storage_path
)


class TestNormalizeDomain:
    """Tests for normalize_domain function."""

    def test_simple_domain(self):
        """Test normalization of simple domain."""
        assert normalize_domain("example.com") == "example_com"

    def test_subdomain(self):
        """Test normalization of subdomain."""
        assert normalize_domain("subdomain.example.com") == "subdomain_example_com"

    def test_domain_with_hyphens(self):
        """Test normalization of domain with hyphens."""
        assert normalize_domain("my-site.example.com") == "my_site_example_com"

    def test_multiple_levels(self):
        """Test normalization of multi-level subdomain."""
        assert normalize_domain("deep.sub.example.com") == "deep_sub_example_com"

    def test_domain_with_numbers(self):
        """Test domain with numbers."""
        assert normalize_domain("test123.example.com") == "test123_example_com"


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_simple_path(self):
        """Test normalization of simple path."""
        assert normalize_path("/about") == "about"

    def test_path_with_hyphens(self):
        """Test normalization of path with hyphens."""
        assert normalize_path("/about-us") == "about_us"

    def test_path_with_trailing_slash(self):
        """Test normalization of path with trailing slash."""
        assert normalize_path("/contact/") == "contact"

    def test_root_path(self):
        """Test normalization of root path."""
        assert normalize_path("/") == "home"

    def test_empty_path(self):
        """Test normalization of empty path."""
        assert normalize_path("") == "home"

    def test_complex_path(self):
        """Test normalization of complex path."""
        assert normalize_path("/about-us/team") == "about_us_team"

    def test_path_with_special_characters(self):
        """Test normalization of path with special characters."""
        assert normalize_path("/contact?query=test") == "contact_query_test"

    def test_path_with_multiple_slashes(self):
        """Test normalization of path with multiple slashes."""
        assert normalize_path("///about///") == "about"

    def test_lowercase_conversion(self):
        """Test that paths are converted to lowercase."""
        assert normalize_path("/About-Us") == "about_us"

    def test_multiple_underscores_removed(self):
        """Test that multiple consecutive underscores are collapsed."""
        assert normalize_path("/about___us") == "about_us"


class TestParseUrl:
    """Tests for parse_url function."""

    def test_simple_url(self):
        """Test parsing of simple URL."""
        domain, norm_domain, norm_path = parse_url("https://example.com/about")
        assert domain == "example.com"
        assert norm_domain == "example_com"
        assert norm_path == "about"

    def test_url_with_subdomain(self):
        """Test parsing of URL with subdomain."""
        domain, norm_domain, norm_path = parse_url("http://sub.example.com/")
        assert domain == "sub.example.com"
        assert norm_domain == "sub_example_com"
        assert norm_path == "home"

    def test_url_with_complex_path(self):
        """Test parsing of URL with complex path."""
        domain, norm_domain, norm_path = parse_url("https://example.com/contact-us")
        assert domain == "example.com"
        assert norm_domain == "example_com"
        assert norm_path == "contact_us"

    def test_url_with_port(self):
        """Test parsing of URL with port."""
        domain, norm_domain, norm_path = parse_url("https://example.com:8080/about")
        # hostname strips port per Python urlparse behavior
        assert domain == "example.com"
        assert norm_domain == "example_com"
        assert norm_path == "about"

    def test_url_without_scheme(self):
        """Test parsing of URL without scheme."""
        domain, norm_domain, norm_path = parse_url("//example.com/about")
        assert domain == "example.com"
        assert norm_domain == "example_com"
        assert norm_path == "about"

    def test_invalid_url_no_domain(self):
        """Test that parsing URL without domain raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL.*no domain found"):
            parse_url("https:///about")

    def test_invalid_url_empty(self):
        """Test that parsing empty URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL.*no domain found"):
            parse_url("")

    def test_url_with_query_string(self):
        """Test parsing URL with query string."""
        domain, norm_domain, norm_path = parse_url("https://example.com/search?q=test")
        assert domain == "example.com"
        assert norm_domain == "example_com"
        # Query string is part of path and gets normalized
        assert "search" in norm_path


class TestGenerateRequestId:
    """Tests for generate_request_id function."""

    def test_with_explicit_timestamp(self):
        """Test request ID generation with explicit timestamp."""
        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("test-1", ts)
        assert request_id == "req_test-1_20250111_120000"

    def test_with_different_base_id(self):
        """Test request ID generation with different base ID."""
        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("123", ts)
        assert request_id == "req_123_20250111_120000"

    def test_with_current_timestamp(self):
        """Test request ID generation with current timestamp (no explicit timestamp)."""
        request_id = generate_request_id("test-1")
        assert request_id.startswith("req_test-1_")
        assert len(request_id) == len("req_test-1_20250111_120000")

    def test_timestamp_format(self):
        """Test that timestamp has correct format."""
        ts = datetime(2025, 12, 31, 23, 59, 59)
        request_id = generate_request_id("test", ts)
        assert request_id == "req_test_20251231_235959"

    def test_with_special_characters_in_id(self):
        """Test request ID with special characters."""
        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("test_request-123", ts)
        assert request_id == "req_test_request-123_20250111_120000"


class TestBuildStoragePath:
    """Tests for build_storage_path function."""

    def test_default_base_path(self):
        """Test building storage path with default base."""
        path = build_storage_path("example_com", "about", "req_123_20250111_120000")
        assert path == "archives/example_com/about/req_123_20250111_120000/"

    def test_custom_base_path(self):
        """Test building storage path with custom base."""
        path = build_storage_path(
            "test_com",
            "home",
            "req_1_20250111_120000",
            "/data"
        )
        assert path == "/data/test_com/home/req_1_20250111_120000/"

    def test_with_complex_path(self):
        """Test building storage path with complex components."""
        path = build_storage_path(
            "subdomain_example_com",
            "about_us",
            "req_test-request-1_20250111_120000"
        )
        assert path == "archives/subdomain_example_com/about_us/req_test-request-1_20250111_120000/"

    def test_ends_with_slash(self):
        """Test that storage path always ends with slash."""
        path = build_storage_path("example_com", "about", "req_123_20250111_120000")
        assert path.endswith("/")

    def test_path_components_preserved(self):
        """Test that all path components are preserved."""
        path = build_storage_path(
            "example_com",
            "contact_us",
            "req_456_20250111_120000",
            "/custom/base"
        )
        assert "/custom/base/" in path or path.startswith("/custom/base/")
        assert "example_com" in path
        assert "contact_us" in path
        assert "req_456_20250111_120000" in path


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow(self):
        """Test complete workflow from URL to storage path."""
        # Parse URL
        url = "https://example.com/about-us"
        domain, norm_domain, norm_path = parse_url(url)

        # Generate request ID
        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("test-1", ts)

        # Build storage path
        storage_path = build_storage_path(norm_domain, norm_path, request_id)

        # Verify final path
        expected = "archives/example_com/about_us/req_test-1_20250111_120000/"
        assert storage_path == expected

    def test_workflow_with_subdomain(self):
        """Test workflow with subdomain URL."""
        url = "https://blog.example.com/contact"
        domain, norm_domain, norm_path = parse_url(url)

        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("456", ts)

        storage_path = build_storage_path(norm_domain, norm_path, request_id)

        expected = "archives/blog_example_com/contact/req_456_20250111_120000/"
        assert storage_path == expected

    def test_workflow_with_root_path(self):
        """Test workflow with root URL."""
        url = "https://example.com/"
        domain, norm_domain, norm_path = parse_url(url)

        ts = datetime(2025, 1, 11, 12, 0, 0)
        request_id = generate_request_id("789", ts)

        storage_path = build_storage_path(norm_domain, norm_path, request_id)

        expected = "archives/example_com/home/req_789_20250111_120000/"
        assert storage_path == expected
