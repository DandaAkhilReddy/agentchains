"""Shared URL validation utilities — SSRF protection for callback/base URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from marketplace.config import settings

_PROD_ENVS = {"production", "prod"}

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_prod() -> bool:
    return settings.environment.lower() in _PROD_ENVS


def is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP belongs to a private, reserved, or loopback range."""
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or any(ip in network for network in _PRIVATE_NETWORKS)
    )


def resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to IP addresses, raising ValueError on failure."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve host: {host}") from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        raw = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw))
        except ValueError:
            continue
    if not addresses:
        raise ValueError(f"No routable IP addresses found for host: {host}")
    return addresses


def validate_url(url: str, *, require_https_in_prod: bool = True) -> str:
    """Validate a URL for SSRF safety and normalize it.

    Checks:
    - Must use http or https scheme
    - Must have a valid host
    - In production: requires HTTPS (if require_https_in_prod=True), blocks localhost
    - Rejects private/reserved IP addresses

    Returns the normalized URL.
    Raises ValueError on invalid or unsafe URLs.
    """
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")
    if not parts.netloc or not parts.hostname:
        raise ValueError("URL must include a valid host")

    if require_https_in_prod and _is_prod() and parts.scheme != "https":
        raise ValueError("HTTPS is required in production")

    host = parts.hostname
    if _is_prod() and host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Localhost URLs are not allowed in production")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        addresses = [literal_ip]
    elif _is_prod():
        addresses = resolve_host_ips(host)
    else:
        addresses = []

    for addr in addresses:
        if is_disallowed_ip(addr):
            raise ValueError("URL resolves to a private or reserved address")

    normalized_path = parts.path or "/"
    normalized = urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, ""))
    return normalized
