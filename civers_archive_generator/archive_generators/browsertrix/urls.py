"""URL identity helpers for matching Browsertrix archive records."""

from urllib.parse import urlsplit, urlunsplit


def normalize_http_url(url: str) -> str:
    """Return an HTTP(S) URL suitable for matching recorded network resources.

    Normalize scheme/host casing, IDNA hostnames, default ports, and an empty root
    path; discard the fragment, which is not part of the HTTP request. Preserve
    credentials, path casing/trailing slashes, percent escapes, and query order.
    This is a comparison helper, not an SSRF check or a full browser URL parser.
    Keep the original URL for reporting and navigation.
    """
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname
    if scheme not in {"http", "https"} or not host:
        raise ValueError("Expected an absolute HTTP(S) URL with a hostname")
    if ":" in host:  # IPv6 literals need brackets when rebuilding the authority.
        host = f"[{host.lower()}]"
    else:
        host = host.encode("idna").decode("ascii").lower()
    port = parsed.port
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        host += f":{port}"
    if "@" in parsed.netloc:
        host = parsed.netloc.rsplit("@", 1)[0] + "@" + host
    normalized = urlunsplit((scheme, host, parsed.path or "/", parsed.query, ""))
    # Preserve an explicitly empty query rather than silently changing its identity.
    if not parsed.query and "?" in url.split("#", 1)[0]:
        normalized += "?"
    return normalized
