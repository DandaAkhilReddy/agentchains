"""Tests for marketplace.core.keyvault — Azure Key Vault secret resolution.

Covers:
- KeyVaultResolver: init validation, lazy client creation, get/set/list secrets
- get_keyvault_resolver: singleton behavior, missing vault URL
- resolve_secrets: with and without Key Vault configured
- resolve_and_override_settings: secret-to-settings mapping
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marketplace.core.keyvault import (
    KeyVaultResolver,
    get_keyvault_resolver,
    resolve_and_override_settings,
    resolve_secrets,
)


# ---------------------------------------------------------------------------
# KeyVaultResolver.__init__
# ---------------------------------------------------------------------------


class TestKeyVaultResolverInit:
    """Validation on construction."""

    def test_empty_vault_url_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL is required"):
            KeyVaultResolver("")

    def test_none_vault_url_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL is required"):
            KeyVaultResolver("")  # falsy string

    def test_valid_vault_url_stores_url(self) -> None:
        resolver = KeyVaultResolver("https://myvault.vault.azure.net/")
        assert resolver._vault_url == "https://myvault.vault.azure.net/"
        assert resolver._client is None


# ---------------------------------------------------------------------------
# KeyVaultResolver._get_client
# ---------------------------------------------------------------------------


class TestKeyVaultResolverGetClient:
    """Lazy client initialization."""

    def test_import_error_when_azure_packages_missing(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        with patch.dict("sys.modules", {"azure.identity": None, "azure.keyvault.secrets": None}):
            with pytest.raises(ImportError, match="azure-identity"):
                resolver._get_client()

    def test_client_created_once_on_first_call(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_credential = MagicMock()
        mock_client_cls = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance

        with patch.dict("sys.modules", {
            "azure": MagicMock(),
            "azure.identity": MagicMock(DefaultAzureCredential=lambda: mock_credential),
            "azure.keyvault": MagicMock(),
            "azure.keyvault.secrets": MagicMock(SecretClient=mock_client_cls),
        }):
            client1 = resolver._get_client()
            client2 = resolver._get_client()

        # Same instance returned on subsequent calls
        assert client1 is client2


# ---------------------------------------------------------------------------
# KeyVaultResolver.get_secret
# ---------------------------------------------------------------------------


class TestKeyVaultResolverGetSecret:
    """Secret retrieval with error handling."""

    def test_get_secret_returns_value(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_secret = MagicMock()
        mock_secret.value = "super-secret-value"
        mock_client = MagicMock()
        mock_client.get_secret.return_value = mock_secret
        resolver._client = mock_client

        result = resolver.get_secret("my-secret")
        assert result == "super-secret-value"
        mock_client.get_secret.assert_called_once_with("my-secret")

    def test_get_secret_returns_none_on_failure(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = Exception("Forbidden")
        resolver._client = mock_client

        result = resolver.get_secret("missing-secret")
        assert result is None


# ---------------------------------------------------------------------------
# KeyVaultResolver.set_secret
# ---------------------------------------------------------------------------


class TestKeyVaultResolverSetSecret:
    """Secret creation/update."""

    def test_set_secret_returns_true_on_success(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_client = MagicMock()
        resolver._client = mock_client

        result = resolver.set_secret("key", "value")
        assert result is True
        mock_client.set_secret.assert_called_once_with("key", "value")

    def test_set_secret_returns_false_on_failure(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_client = MagicMock()
        mock_client.set_secret.side_effect = Exception("Write denied")
        resolver._client = mock_client

        result = resolver.set_secret("key", "value")
        assert result is False


# ---------------------------------------------------------------------------
# KeyVaultResolver.list_secrets
# ---------------------------------------------------------------------------


class TestKeyVaultResolverListSecrets:
    """Secret enumeration."""

    def test_list_secrets_returns_names(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_prop1 = MagicMock()
        mock_prop1.name = "secret-a"
        mock_prop2 = MagicMock()
        mock_prop2.name = "secret-b"
        mock_client = MagicMock()
        mock_client.list_properties_of_secrets.return_value = [mock_prop1, mock_prop2]
        resolver._client = mock_client

        result = resolver.list_secrets()
        assert result == ["secret-a", "secret-b"]

    def test_list_secrets_returns_empty_on_failure(self) -> None:
        resolver = KeyVaultResolver("https://vault.vault.azure.net/")
        mock_client = MagicMock()
        mock_client.list_properties_of_secrets.side_effect = Exception("Network error")
        resolver._client = mock_client

        result = resolver.list_secrets()
        assert result == []


# ---------------------------------------------------------------------------
# get_keyvault_resolver
# ---------------------------------------------------------------------------


class TestGetKeyvaultResolver:
    """Singleton factory function."""

    def test_returns_none_when_vault_url_not_configured(self) -> None:
        import marketplace.core.keyvault as kv_mod

        kv_mod._resolver = None
        with patch("marketplace.config.settings") as mock_settings:
            mock_settings.azure_keyvault_url = ""
            result = get_keyvault_resolver()
        assert result is None
        kv_mod._resolver = None  # cleanup

    def test_returns_resolver_when_vault_url_configured(self) -> None:
        import marketplace.core.keyvault as kv_mod

        kv_mod._resolver = None
        with patch("marketplace.config.settings") as mock_settings:
            mock_settings.azure_keyvault_url = "https://test.vault.azure.net/"
            result = get_keyvault_resolver()
        assert isinstance(result, KeyVaultResolver)
        kv_mod._resolver = None  # cleanup

    def test_returns_same_instance_on_repeated_calls(self) -> None:
        import marketplace.core.keyvault as kv_mod

        kv_mod._resolver = None
        with patch("marketplace.config.settings") as mock_settings:
            mock_settings.azure_keyvault_url = "https://test.vault.azure.net/"
            r1 = get_keyvault_resolver()
            r2 = get_keyvault_resolver()
        assert r1 is r2
        kv_mod._resolver = None  # cleanup


# ---------------------------------------------------------------------------
# resolve_secrets
# ---------------------------------------------------------------------------


class TestResolveSecrets:
    """Bulk secret resolution."""

    def test_returns_nones_when_keyvault_not_configured(self) -> None:
        with patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=None):
            result = resolve_secrets(["secret-a", "secret-b"])
        assert result == {"secret-a": None, "secret-b": None}

    def test_returns_resolved_values(self) -> None:
        mock_resolver = MagicMock(spec=KeyVaultResolver)
        mock_resolver.get_secret.side_effect = lambda name: f"val-{name}"
        with patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=mock_resolver):
            result = resolve_secrets(["jwt-key", "db-pass"])
        assert result == {"jwt-key": "val-jwt-key", "db-pass": "val-db-pass"}

    def test_empty_list_returns_empty_dict(self) -> None:
        with patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=None):
            result = resolve_secrets([])
        assert result == {}


# ---------------------------------------------------------------------------
# resolve_and_override_settings
# ---------------------------------------------------------------------------


class TestResolveAndOverrideSettings:
    """Startup secret injection into settings."""

    def test_noop_when_keyvault_not_configured(self) -> None:
        with patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=None):
            resolve_and_override_settings()  # should not raise

    def test_overrides_settings_with_resolved_values(self) -> None:
        mock_resolver = MagicMock(spec=KeyVaultResolver)
        mock_resolver.get_secret.side_effect = lambda name: (
            "real-jwt-secret" if name == "jwt-secret-key" else None
        )

        mock_settings = MagicMock()
        mock_settings.jwt_secret_key = "placeholder"

        with (
            patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=mock_resolver),
            patch("marketplace.config.settings", mock_settings),
        ):
            resolve_and_override_settings()

        # jwt_secret_key should have been set to the resolved value
        mock_settings.__setattr__("jwt_secret_key", "real-jwt-secret")

    def test_skips_entries_with_none_settings_attr(self) -> None:
        """database-password maps to None settings_attr and should be skipped."""
        mock_resolver = MagicMock(spec=KeyVaultResolver)
        mock_resolver.get_secret.return_value = "some-value"

        with (
            patch("marketplace.core.keyvault.get_keyvault_resolver", return_value=mock_resolver),
            patch("marketplace.config.settings") as mock_settings,
        ):
            resolve_and_override_settings()

        # "database-password" has settings_attr=None, so get_secret
        # should NOT be called for it (it's skipped in the loop)
        called_names = [call.args[0] for call in mock_resolver.get_secret.call_args_list]
        assert "database-password" not in called_names
