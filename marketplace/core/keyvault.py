"""Azure Key Vault secret resolver.

Resolves secrets from Azure Key Vault at startup. Uses managed identity
when running in Azure Container Apps, or falls back to environment
variables for local development.

Usage:
    from marketplace.core.keyvault import resolve_secrets
    resolved = await resolve_secrets(["jwt-secret-key", "db-password"])
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class KeyVaultResolver:
    """Resolve secrets from Azure Key Vault."""

    def __init__(self, vault_url: str):
        if not vault_url:
            raise ValueError("AZURE_KEYVAULT_URL is required for Key Vault integration")
        self._vault_url = vault_url
        self._client = None

    def _get_client(self):
        """Lazy-initialize the SecretClient with DefaultAzureCredential."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                credential = DefaultAzureCredential()
                self._client = SecretClient(
                    vault_url=self._vault_url,
                    credential=credential,
                )
                logger.info("Key Vault client initialized: %s", self._vault_url)
            except ImportError:
                raise ImportError(
                    "azure-identity and azure-keyvault-secrets are required. "
                    "Install with: pip install azure-identity azure-keyvault-secrets"
                )
        return self._client

    def get_secret(self, name: str) -> str | None:
        """Get a secret value from Key Vault."""
        try:
            client = self._get_client()
            secret = client.get_secret(name)
            return secret.value
        except Exception as e:
            logger.warning("Failed to get secret '%s' from Key Vault: %s", name, e)
            return None

    def set_secret(self, name: str, value: str) -> bool:
        """Set a secret value in Key Vault."""
        try:
            client = self._get_client()
            client.set_secret(name, value)
            return True
        except Exception as e:
            logger.error("Failed to set secret '%s' in Key Vault: %s", name, e)
            return False

    def list_secrets(self) -> list[str]:
        """List all secret names in the vault."""
        try:
            client = self._get_client()
            return [s.name for s in client.list_properties_of_secrets()]
        except Exception as e:
            logger.error("Failed to list secrets from Key Vault: %s", e)
            return []


_resolver: KeyVaultResolver | None = None


def get_keyvault_resolver() -> KeyVaultResolver | None:
    """Get the Key Vault resolver singleton."""
    global _resolver
    from marketplace.config import settings

    vault_url = getattr(settings, "azure_keyvault_url", "")
    if not vault_url:
        return None
    if _resolver is None:
        _resolver = KeyVaultResolver(vault_url)
    return _resolver


def resolve_secrets(secret_names: list[str]) -> dict[str, str | None]:
    """Resolve multiple secrets from Key Vault.

    Returns a mapping of secret name -> value (or None if not found).
    """
    resolver = get_keyvault_resolver()
    if not resolver:
        logger.info("Key Vault not configured — secrets will use env vars")
        return {name: None for name in secret_names}

    results = {}
    for name in secret_names:
        results[name] = resolver.get_secret(name)
    return results


def resolve_and_override_settings() -> None:
    """Resolve secrets from Key Vault and override settings values.

    Called at startup to replace placeholder settings with real secrets.
    Maps Key Vault secret names to settings attributes.
    """
    resolver = get_keyvault_resolver()
    if not resolver:
        return

    from marketplace.config import settings

    _KV_SETTINGS_MAP = {
        "jwt-secret-key": "jwt_secret_key",
        "event-signing-secret": "event_signing_secret",
        "memory-encryption-key": "memory_encryption_key",
        "stripe-secret-key": "stripe_secret_key",
        "stripe-webhook-secret": "stripe_webhook_secret",
        "razorpay-key-id": "razorpay_key_id",
        "razorpay-key-secret": "razorpay_key_secret",
        "database-password": None,  # Handled via connection string
    }

    resolved = 0
    for kv_name, settings_attr in _KV_SETTINGS_MAP.items():
        if not settings_attr:
            continue
        value = resolver.get_secret(kv_name)
        if value is not None:
            setattr(settings, settings_attr, value)
            resolved += 1

    if resolved > 0:
        logger.info("Resolved %d secrets from Key Vault", resolved)
