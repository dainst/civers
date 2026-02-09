"""
URL parsing utilities for extracting domain and path information.

These utilities parse URLs and normalize them for filesystem storage,
following the pattern: archives/{domain}/{path}/{request_id}/
"""

import re
from datetime import datetime
from typing import Tuple
from urllib.parse import urlparse


def normalize_domain(domain: str) -> str:
    """
    Normalize domain for filesystem use.

    Replaces dots and hyphens with underscores.

    Args:
        domain: Domain name (e.g., "example.com")

    Returns:
        Normalized domain (e.g., "example_com")

    Examples:
        >>> normalize_domain("example.com")
        'example_com'
        >>> normalize_domain("subdomain.example.com")
        'subdomain_example_com'
        >>> normalize_domain("my-site.example.com")
        'my_site_example_com'
    """
    return domain.replace('.', '_').replace('-', '_')


def normalize_path(path: str) -> str:
    """
    Normalize URL path for filesystem use.

    Removes leading/trailing slashes, replaces special characters with underscores,
    and handles the root path as 'home'.

    Args:
        path: URL path (e.g., "/about-us")

    Returns:
        Normalized path (e.g., "about_us")

    Examples:
        >>> normalize_path("/about")
        'about'
        >>> normalize_path("/about-us")
        'about_us'
        >>> normalize_path("/contact/")
        'contact'
        >>> normalize_path("/")
        'home'
        >>> normalize_path("")
        'home'
    """
    # Remove leading/trailing slashes
    path = path.strip('/')

    # Handle root path
    if not path:
        return 'home'

    # Replace special characters with underscores
    path = re.sub(r'[^\w\-]', '_', path)
    path = path.replace('-', '_')

    # Remove multiple underscores
    path = re.sub(r'_+', '_', path)

    return path.lower()


def parse_url(url: str) -> Tuple[str, str, str]:
    """
    Parse URL and extract components for storage.

    Extracts the domain and path from a URL and normalizes them for
    filesystem storage.

    Args:
        url: Full URL (e.g., "https://example.com/about")

    Returns:
        Tuple of (domain, normalized_domain, normalized_path)

    Raises:
        ValueError: If URL is invalid or has no domain

    Examples:
        >>> parse_url("https://example.com/about")
        ('example.com', 'example_com', 'about')
        >>> parse_url("http://sub.example.com/")
        ('sub.example.com', 'sub_example_com', 'home')
        >>> parse_url("https://example.com/contact-us")
        ('example.com', 'example_com', 'contact_us')
    """
    parsed = urlparse(url)

    # Extract domain (hostname excludes port)
    domain = parsed.hostname
    if not domain:
        # Fallback to netloc if hostname fails (e.g. invalid URL)
        domain = parsed.netloc.split(':')[0] if ':' in parsed.netloc else parsed.netloc
        
    if not domain:
        raise ValueError(f"Invalid URL: {url} - no domain found")

    # Normalize for filesystem
    normalized_domain = normalize_domain(domain)
    normalized_path = normalize_path(parsed.path)

    return domain, normalized_domain, normalized_path


def generate_url_id(url: str) -> str:
    """
    Generate a url_id from a URL for archive page linking.

    Creates a filesystem-safe identifier by combining the normalized domain
    and path. Query parameters are stripped as they don't affect the archive page.

    Args:
        url: Full URL (e.g., "https://example.com/about?q=test")

    Returns:
        url_id (e.g., "example_com_about")

    Examples:
        >>> generate_url_id("https://example.com/about")
        'example_com_about'
        >>> generate_url_id("https://example.com/entity/123?fl=20&q=test")
        'example_com_entity_123'
        >>> generate_url_id("https://arachne.test.dainst.org/entity/1075882?fl=20")
        'arachne_test_dainst_org_entity_1075882'
    """
    _, normalized_domain, normalized_path = parse_url(url)
    return f"{normalized_domain}_{normalized_path}"


def generate_request_id(request_id: str, timestamp: datetime = None) -> str:
    """
    Generate full request ID with timestamp.

    Combines a base request ID with a timestamp to create a unique
    request identifier in the format: req_{id}_{YYYYMMDD_HHMMSS}

    Args:
        request_id: Base request ID (e.g., "test-1")
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Full request ID (e.g., "req_test-1_20250111_120000")

    Examples:
        >>> from datetime import datetime
        >>> ts = datetime(2025, 1, 11, 12, 0, 0)
        >>> generate_request_id("test-1", ts)
        'req_test-1_20250111_120000'
        >>> generate_request_id("123", ts)
        'req_123_20250111_120000'
    """
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
    return f"req_{request_id}_{timestamp_str}"


def build_storage_path(
    normalized_domain: str,
    normalized_path: str,
    request_id: str,
    base_path: str = "archives"
) -> str:
    """
    Build full storage path for a request.

    Creates the directory path following the structure:
    {base_path}/{domain}/{path}/{request_id}/

    Args:
        normalized_domain: Normalized domain (e.g., "example_com")
        normalized_path: Normalized path (e.g., "about")
        request_id: Full request ID (e.g., "req_test-1_20250111_120000")
        base_path: Base storage directory (default: "archives")

    Returns:
        Full path (e.g., "archives/example_com/about/req_test-1_20250111_120000/")

    Examples:
        >>> build_storage_path("example_com", "about", "req_123_20250111_120000")
        'archives/example_com/about/req_123_20250111_120000/'
        >>> build_storage_path("test_com", "home", "req_1_20250111_120000", "/data")
        '/data/test_com/home/req_1_20250111_120000/'
    """
    return f"{base_path}/{normalized_domain}/{normalized_path}/{request_id}/"
