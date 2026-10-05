"""Check URL scheme and host-address restrictions before capture."""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from archive_services.url_guard import UrlGuard

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _resolving_to(*ips):
    loop = Mock()
    loop.getaddrinfo = AsyncMock(
        return_value=[(None, None, None, None, (ip, 0)) for ip in ips]
    )
    return loop


def _failing_to_resolve():
    loop = Mock()
    loop.getaddrinfo = AsyncMock(side_effect=OSError("name resolution failed"))
    return loop


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.1",
        "192.168.1.5",
        "127.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "0.0.0.0",
        "172.16.0.1",
        "100.64.0.1",       # Shared address range.
        "240.0.0.1",        # reserved
        "::1",              # IPv6 loopback
        "fd00::1",          # IPv6 unique local
        "fe80::1",          # IPv6 link-local
        "::ffff:127.0.0.1", # Loopback address stored in IPv6 form.
        "::ffff:10.0.0.1",
    ],
)
async def test_blocks_private_and_local_addresses(ip):
    with patch("asyncio.get_running_loop", return_value=_resolving_to(ip)):
        with pytest.raises(ValueError, match="prohibited private/local IP"):
            await UrlGuard().validate("https://internal.example/x")


async def test_allows_public_address():
    with patch("asyncio.get_running_loop", return_value=_resolving_to("93.184.216.34")):
        await UrlGuard().validate("https://example.com/x")


async def test_every_resolved_address_is_checked_not_only_the_first():
    """A host with one public and one private record must not pass on the public one."""
    with patch(
        "asyncio.get_running_loop",
        return_value=_resolving_to("93.184.216.34", "10.0.0.1"),
    ):
        with pytest.raises(ValueError, match="10.0.0.1"):
            await UrlGuard().validate("https://rebind.example/x")


async def test_unresolvable_hostname_is_refused():
    """Allowing it through leaves the decision to a browser that resolves it later."""
    with patch("asyncio.get_running_loop", return_value=_failing_to_resolve()):
        with pytest.raises(ValueError, match="Could not resolve hostname"):
            await UrlGuard().validate("https://does-not-resolve.invalid/x")


async def test_url_without_hostname_is_refused():
    with pytest.raises(ValueError, match="names no host"):
        await UrlGuard().validate("https:///just/a/path")


async def test_url_without_a_scheme_is_refused():
    with pytest.raises(ValueError, match="is not permitted"):
        await UrlGuard().validate("not-a-url")


@pytest.mark.parametrize("ip", ["8.8.8.8", "2606:4700:4700::1111", "::ffff:93.184.216.34"])
async def test_globally_routable_addresses_pass(ip):
    with patch("asyncio.get_running_loop", return_value=_resolving_to(ip)):
        await UrlGuard().validate("https://example.com/x")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://127.0.0.1:11211/x",
        "ftp://internal.example/x",
        "data:text/html,<script>alert(1)</script>",
    ],
)
async def test_only_http_and_https_are_permitted(url):
    with pytest.raises(ValueError, match="is not permitted"):
        await UrlGuard().validate(url)
