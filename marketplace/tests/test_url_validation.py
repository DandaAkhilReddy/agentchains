"""Tests for marketplace.core.url_validation — SSRF protection and URL normalization.

Covers:
- validate_url: scheme enforcement, host validation, HTTPS in prod, SSRF blocking
- is_disallowed_ip: private/reserved/loopback/link-local detection
- resolve_host_ips: DNS resolution success and failure paths
- _is_prod: environment detection
"""

from __future__ import annotations

import ipaddress
import socket
from unittest.mock import patch

import pytest

from marketplace.core.url_validation import (
    is_disallowed_ip,
    resolve_host_ips,
    validate_url,
)


# ---------------------------------------------------------------------------
# is_disallowed_ip
# ---------------------------------------------------------------------------


class TestIsDisallowedIp:
    """Unit tests for is_disallowed_ip — private/reserved IP detection."""

    def test_loopback_ipv4_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("127.0.0.1")) is True

    def test_loopback_ipv6_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("::1")) is True

    def test_private_10_network_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("10.0.0.1")) is True

    def test_private_172_network_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("172.16.0.1")) is True

    def test_private_192_network_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("192.168.1.1")) is True

    def test_link_local_ipv4_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("169.254.1.1")) is True

    def test_link_local_ipv6_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("fe80::1")) is True

    def test_unique_local_ipv6_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("fc00::1")) is True

    def test_multicast_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("224.0.0.1")) is True

    def test_unspecified_is_disallowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("0.0.0.0")) is True

    def test_public_ipv4_is_allowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("8.8.8.8")) is False

    def test_public_ipv6_is_allowed(self) -> None:
        assert is_disallowed_ip(ipaddress.ip_address("2607:f8b0:4004:800::200e")) is False


# ---------------------------------------------------------------------------
# resolve_host_ips
# ---------------------------------------------------------------------------


class TestResolveHostIps:
    """Unit tests for resolve_host_ips — DNS resolution wrapper."""

    def test_successful_resolution_returns_ip_list(self) -> None:
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        with patch("marketplace.core.url_validation.socket.getaddrinfo", return_value=fake_infos):
            result = resolve_host_ips("example.com")
        assert len(result) == 1
        assert result[0] == ipaddress.ip_address("93.184.216.34")

    def test_resolution_failure_raises_valueerror(self) -> None:
        with patch(
            "marketplace.core.url_validation.socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            with pytest.raises(ValueError, match="Unable to resolve host"):
                resolve_host_ips("nonexistent.invalid")

    def test_no_routable_addresses_raises_valueerror(self) -> None:
        """getaddrinfo returns entries but none have valid IPs."""
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("not-an-ip", 0)),
        ]
        with patch("marketplace.core.url_validation.socket.getaddrinfo", return_value=fake_infos):
            with pytest.raises(ValueError, match="No routable IP addresses"):
                resolve_host_ips("weird.host")

    def test_multiple_addresses_returned(self) -> None:
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.2.3.4", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("5.6.7.8", 0)),
        ]
        with patch("marketplace.core.url_validation.socket.getaddrinfo", return_value=fake_infos):
            result = resolve_host_ips("multi.example.com")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# validate_url — development mode
# ---------------------------------------------------------------------------


class TestValidateUrlDev:
    """validate_url in development (non-production) environment."""

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_valid_https_url_passes(self, _mock: object) -> None:
        result = validate_url("https://example.com/path?q=1")
        assert result == "https://example.com/path?q=1"

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_valid_http_url_passes_in_dev(self, _mock: object) -> None:
        result = validate_url("http://example.com/page")
        assert result == "http://example.com/page"

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_empty_url_raises(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="http or https"):
            validate_url("")

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_none_coerced_to_empty_raises(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="http or https"):
            validate_url(None)  # type: ignore[arg-type]

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_ftp_scheme_rejected(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="http or https"):
            validate_url("ftp://files.example.com/data")

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_missing_host_rejected(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="valid host"):
            validate_url("http://")

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_private_ip_literal_rejected(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://192.168.1.1/admin")

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_loopback_ip_literal_rejected(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://127.0.0.1/secret")

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_path_normalized_to_slash(self, _mock: object) -> None:
        result = validate_url("https://example.com")
        assert result == "https://example.com/"

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_whitespace_stripped(self, _mock: object) -> None:
        result = validate_url("  https://example.com/path  ")
        assert result == "https://example.com/path"

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_fragment_stripped(self, _mock: object) -> None:
        """URL fragments are removed during normalization."""
        result = validate_url("https://example.com/page#section")
        assert "#" not in result

    @patch("marketplace.core.url_validation._is_prod", return_value=False)
    def test_query_params_preserved(self, _mock: object) -> None:
        result = validate_url("https://example.com/api?key=val&foo=bar")
        assert "key=val" in result
        assert "foo=bar" in result


# ---------------------------------------------------------------------------
# validate_url — production mode
# ---------------------------------------------------------------------------


class TestValidateUrlProd:
    """validate_url in production environment — stricter rules."""

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_http_rejected_in_prod(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="HTTPS is required in production"):
            validate_url("http://example.com/page")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_http_allowed_when_require_https_disabled(self, _mock: object) -> None:
        result = validate_url("http://example.com/page", require_https_in_prod=False)
        assert result.startswith("http://")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_localhost_rejected_in_prod(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="Localhost URLs are not allowed"):
            validate_url("https://localhost/api")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_127_0_0_1_rejected_in_prod(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="Localhost URLs are not allowed"):
            validate_url("https://127.0.0.1/api")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_ipv6_loopback_rejected_in_prod(self, _mock: object) -> None:
        with pytest.raises(ValueError, match="Localhost URLs are not allowed"):
            validate_url("https://[::1]/api")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_hostname_resolving_to_private_ip_rejected(self, _mock: object) -> None:
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0)),
        ]
        with patch(
            "marketplace.core.url_validation.socket.getaddrinfo", return_value=fake_infos
        ):
            with pytest.raises(ValueError, match="private or reserved"):
                validate_url("https://internal.corp.example.com/api")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_hostname_resolving_to_public_ip_passes(self, _mock: object) -> None:
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        with patch(
            "marketplace.core.url_validation.socket.getaddrinfo", return_value=fake_infos
        ):
            result = validate_url("https://example.com/api")
        assert result == "https://example.com/api"

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_unresolvable_hostname_raises(self, _mock: object) -> None:
        with patch(
            "marketplace.core.url_validation.socket.getaddrinfo",
            side_effect=socket.gaierror("DNS failed"),
        ):
            with pytest.raises(ValueError, match="Unable to resolve host"):
                validate_url("https://does-not-exist.invalid/api")

    @patch("marketplace.core.url_validation._is_prod", return_value=True)
    def test_https_public_ip_literal_passes(self, _mock: object) -> None:
        result = validate_url("https://93.184.216.34/path")
        assert result == "https://93.184.216.34/path"
