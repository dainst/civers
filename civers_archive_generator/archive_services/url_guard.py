"""Check request URLs before starting a capture."""

import asyncio
import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Captures accept only HTTP and HTTPS URLs.
ALLOWED_SCHEMES = frozenset({"http", "https"})


class UrlGuard:
    """Reject non-HTTP URLs and hosts that resolve to nonpublic addresses."""

    async def validate(self, url: str) -> None:
        """Raise ValueError for a blocked scheme, missing host or nonpublic address.

        Unresolved hosts are also rejected.
        """
        parsed = urlparse(url)

        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(
                f"URL scheme '{parsed.scheme}' is not permitted; "
                f"allowed: {', '.join(sorted(ALLOWED_SCHEMES))}"
            )

        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"URL names no host: {url!r}")

        for ip in await self._resolve(hostname):
            if self._is_prohibited(ip):
                raise ValueError(
                    f"URL resolves to a prohibited private/local IP address: {ip}"
                )

    @staticmethod
    async def _resolve(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Resolve all host addresses; raise ValueError if none are usable."""
        try:
            results = await asyncio.get_running_loop().getaddrinfo(hostname, None)
        except OSError as exc:
            raise ValueError(
                f"Could not resolve hostname '{hostname}': {exc}"
            ) from exc

        addresses = []
        for result in results:
            try:
                addresses.append(ipaddress.ip_address(result[4][0]))
            except ValueError:
                logger.warning(f"Ignoring unparseable address for {hostname}: {result[4][0]!r}")
        if not addresses:
            raise ValueError(f"Hostname '{hostname}' resolved to no usable address")
        return addresses

    @staticmethod
    def _is_prohibited(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Reject nonpublic and multicast addresses, including mapped IPv4 addresses."""
        # Check mapped IPv4 addresses, such as ::ffff:127.0.0.1, as IPv4.
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return not ip.is_global or ip.is_multicast
