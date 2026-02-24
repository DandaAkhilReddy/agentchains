"""Comprehensive tests for async_tasks, creator_auth, and keyvault modules.

Covers:
- async_tasks.fire_and_forget: scheduling, task tracking, error logging, cancel, no-loop fallback
- async_tasks.drain_background_tasks: empty set, pending tasks, timeout and cancel
- creator_auth.hash_password / verify_password: bcrypt round-trips and rejection
- creator_auth.create_creator_token: payload claims, exp, jti uniqueness
- creator_auth.get_current_creator_id: happy path, missing header, wrong scheme,
  wrong type, expired token, tampered token, missing sub
- keyvault.KeyVaultResolver: init guards, lazy client, get/set/list with mocked SDK
- keyvault.get_keyvault_resolver: no-URL returns None, URL returns singleton
- keyvault.resolve_secrets: no-resolver path, with resolver path, partial failures
- keyvault.resolve_and_override_settings: no-resolver no-op, updates settings attrs,
  skips None-mapped keys, skips secrets that return None
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt

from marketplace.config import settings
from marketplace.core.async_tasks import drain_background_tasks, fire_and_forget, _PENDING_TASKS
from marketplace.core.creator_auth import (
    create_creator_token,
    get_current_creator_id,
    hash_password,
    verify_password,
)
from marketplace.core.exceptions import UnauthorizedError


# ===========================================================================
# Helpers
# ===========================================================================


async def _instant_coro() -> str:
    """Coroutine that completes immediately."""
    return "done"


async def _slow_coro(delay: float = 5.0) -> None:
    """Coroutine that sleeps — used to test drain timeout/cancel."""
    await asyncio.sleep(delay)


async def _failing_coro() -> None:
    """Coroutine that raises — used to test error logging."""
    raise ValueError("boom from background task")


# ===========================================================================
# async_tasks.py — fire_and_forget
# ===========================================================================


class TestFireAndForget:
    """Tests for the fire_and_forget scheduler."""

    async def test_returns_task_object(self):
        """fire_and_forget should return an asyncio.Task."""
        task = fire_and_forget(_instant_coro())
        assert isinstance(task, asyncio.Task)
        await drain_background_tasks()

    async def test_task_added_to_pending_set(self):
        """The task must appear in _PENDING_TASKS before it completes."""
        task = fire_and_forget(_slow_coro(delay=10.0))
        assert task in _PENDING_TASKS
        task.cancel()
        await drain_background_tasks()

    async def test_task_removed_from_pending_set_after_completion(self):
        """After the coroutine finishes, _on_done removes the task."""
        task = fire_and_forget(_instant_coro())
        await asyncio.sleep(0)          # yield to allow the task to run
        await asyncio.sleep(0)          # second yield for the callback
        assert task not in _PENDING_TASKS

    async def test_task_name_is_set(self):
        """When task_name is provided it should appear in task.get_name()."""
        task = fire_and_forget(_instant_coro(), task_name="my-named-task")
        assert task.get_name() == "my-named-task"
        await drain_background_tasks()

    async def test_unnamed_task_has_default_name(self):
        """When task_name is None the task still gets a non-empty name from asyncio."""
        task = fire_and_forget(_instant_coro())
        assert task.get_name()          # asyncio assigns "Task-N" by default
        await drain_background_tasks()

    async def test_failing_task_logs_exception(self, caplog):
        """A failing background task should be logged at ERROR/exception level."""
        with caplog.at_level(logging.ERROR, logger="marketplace.core.async_tasks"):
            task = fire_and_forget(_failing_coro(), task_name="fail-task")
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert "Background task failed" in caplog.text

    async def test_failing_task_does_not_propagate_exception(self):
        """An exception inside fire_and_forget must NOT bubble up to the caller."""
        task = fire_and_forget(_failing_coro())
        # Simply awaiting drain must not raise.
        await drain_background_tasks()

    async def test_cancelled_task_does_not_log_error(self, caplog):
        """CancelledError is silently swallowed — no error log produced."""
        with caplog.at_level(logging.ERROR, logger="marketplace.core.async_tasks"):
            task = fire_and_forget(_slow_coro(delay=10.0))
            task.cancel()
            await drain_background_tasks()

        assert "Background task failed" not in caplog.text

    async def test_no_running_loop_returns_none(self):
        """RuntimeError from create_task (no loop) must return None gracefully."""
        with patch("asyncio.create_task", side_effect=RuntimeError("no running loop")):
            result = fire_and_forget(_instant_coro())
        assert result is None


# ===========================================================================
# async_tasks.py — drain_background_tasks
# ===========================================================================


class TestDrainBackgroundTasks:
    """Tests for drain_background_tasks."""

    async def test_drain_with_no_pending_tasks_returns_immediately(self):
        """When _PENDING_TASKS is empty, drain should return without waiting."""
        # Ensure set is empty (autouse fixture handles db isolation but not this)
        _PENDING_TASKS.clear()
        # Should complete instantly without blocking
        await drain_background_tasks(timeout_seconds=0.1)

    async def test_drain_waits_for_fast_task(self):
        """drain_background_tasks should let a fast task finish normally."""
        results: list[str] = []

        async def _appender():
            results.append("finished")

        fire_and_forget(_appender())
        await drain_background_tasks(timeout_seconds=1.0)
        assert "finished" in results

    async def test_drain_cancels_slow_tasks_after_timeout(self):
        """Tasks that exceed the timeout should be cancelled by drain."""
        task = fire_and_forget(_slow_coro(delay=30.0), task_name="slow-drain-test")
        await drain_background_tasks(timeout_seconds=0.05)
        # After drain, the task should be done (cancelled)
        assert task.done()

    async def test_drain_multiple_pending_tasks(self):
        """drain_background_tasks handles several concurrent tasks."""
        completed: list[int] = []

        async def _work(n: int):
            completed.append(n)

        for i in range(5):
            fire_and_forget(_work(i))

        await drain_background_tasks(timeout_seconds=1.0)
        assert sorted(completed) == [0, 1, 2, 3, 4]

    async def test_drain_skips_already_done_tasks(self):
        """Tasks that finished before drain is called are not re-awaited."""
        task = fire_and_forget(_instant_coro())
        await asyncio.sleep(0)          # let the task finish
        await asyncio.sleep(0)
        # Now drain — should not raise even though task is already done
        await drain_background_tasks(timeout_seconds=0.1)


# ===========================================================================
# creator_auth.py — hash_password / verify_password
# ===========================================================================


class TestHashPassword:
    """Tests for bcrypt hashing helpers."""

    async def test_hash_returns_bcrypt_format(self):
        """hash_password must return a string starting with '$2b$' or '$2a$'."""
        hashed = hash_password("MyP@ssw0rd")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    async def test_hash_is_60_characters(self):
        """Bcrypt hashes are exactly 60 characters long."""
        hashed = hash_password("test-password")
        assert len(hashed) == 60

    async def test_same_password_different_hashes(self):
        """Each call must produce a unique salt/hash (no constant salt)."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    async def test_verify_correct_password_returns_true(self):
        """verify_password should return True for the matching password."""
        pw = "correct-horse-battery-staple"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    async def test_verify_wrong_password_returns_false(self):
        """verify_password should return False for a wrong password."""
        hashed = hash_password("right-password")
        assert verify_password("wrong-password", hashed) is False

    async def test_verify_empty_password_returns_false(self):
        """verify_password should return False for an empty string against a real hash."""
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False

    async def test_verify_unicode_password(self):
        """Unicode passwords should hash and verify correctly."""
        pw = "P@ssw0rd\u00e9\u00e0\u00fc"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True
        assert verify_password("wrong", hashed) is False


# ===========================================================================
# creator_auth.py — create_creator_token
# ===========================================================================


class TestCreateCreatorToken:
    """Tests for JWT creation for creator accounts."""

    async def test_returns_non_empty_string(self):
        """create_creator_token must return a non-empty string."""
        token = create_creator_token("c-1", "user@example.com")
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_payload_contains_type_creator(self):
        """Token payload must carry type='creator'."""
        token = create_creator_token("c-2", "alice@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        assert payload["type"] == "creator"

    async def test_payload_contains_sub(self):
        """Token sub claim must equal the creator_id passed in."""
        creator_id = "creator-abc-999"
        token = create_creator_token(creator_id, "bob@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        assert payload["sub"] == creator_id

    async def test_payload_contains_email(self):
        """Token must embed the email address."""
        email = "carol@example.com"
        token = create_creator_token("c-3", email)
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        assert payload["email"] == email

    async def test_payload_contains_valid_jti(self):
        """jti claim must be a valid UUID string."""
        token = create_creator_token("c-4", "dave@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        assert "jti" in payload
        # Will raise ValueError if not a valid UUID
        parsed = uuid.UUID(payload["jti"])
        assert str(parsed) == payload["jti"]

    async def test_jti_is_unique_per_token(self):
        """Two tokens for the same creator must have different jti values."""
        t1 = create_creator_token("c-5", "same@example.com")
        t2 = create_creator_token("c-5", "same@example.com")
        p1 = jwt.decode(t1, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], audience="agentchains-marketplace")
        p2 = jwt.decode(t2, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], audience="agentchains-marketplace")
        assert p1["jti"] != p2["jti"]

    async def test_exp_is_in_the_future(self):
        """Expiry claim must be at least one hour from now."""
        token = create_creator_token("c-6", "exp@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp_dt >= datetime.now(timezone.utc) + timedelta(minutes=59)

    async def test_iat_is_present_and_recent(self):
        """iat (issued-at) claim must be close to the current time."""
        token = create_creator_token("c-7", "iat@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
        )
        assert "iat" in payload
        iat_dt = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        # iat should be within the last minute
        assert abs((datetime.now(timezone.utc) - iat_dt).total_seconds()) < 60


# ===========================================================================
# creator_auth.py — get_current_creator_id
# ===========================================================================


class TestGetCurrentCreatorId:
    """Tests for token extraction / validation for creator endpoints."""

    async def test_valid_creator_token_returns_creator_id(self):
        """Should return creator_id from a well-formed creator Bearer token."""
        token = create_creator_token("creator-42", "valid@test.com")
        result = get_current_creator_id(f"Bearer {token}")
        assert result == "creator-42"

    async def test_missing_authorization_header_raises(self):
        """None authorization must raise UnauthorizedError with clear message."""
        with pytest.raises(UnauthorizedError, match="Missing Authorization header"):
            get_current_creator_id(None)

    async def test_empty_string_authorization_raises(self):
        """Empty string authorization must raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            get_current_creator_id("")

    async def test_wrong_scheme_raises(self):
        """Using 'Token' instead of 'Bearer' must raise UnauthorizedError."""
        token = create_creator_token("c-1", "a@b.com")
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_creator_id(f"Token {token}")

    async def test_three_part_authorization_raises(self):
        """Header with 3 space-separated parts must raise UnauthorizedError."""
        token = create_creator_token("c-1", "a@b.com")
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_creator_id(f"Bearer {token} extra")

    async def test_agent_token_raises_not_creator(self):
        """An agent JWT (no type=creator claim) must raise UnauthorizedError."""
        from marketplace.core.auth import create_access_token
        agent_token = create_access_token("agent-1", "SomeAgent")
        with pytest.raises(UnauthorizedError, match="Not a creator token"):
            get_current_creator_id(f"Bearer {agent_token}")

    async def test_expired_token_raises(self):
        """A token with exp in the past must raise UnauthorizedError."""
        expired_payload = {
            "sub": "creator-old",
            "email": "old@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_creator_id(f"Bearer {token}")

    async def test_tampered_signature_raises(self):
        """Token signed with a wrong key must raise UnauthorizedError."""
        payload = {
            "sub": "creator-hacked",
            "email": "hacker@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        bad_token = jwt.encode(payload, "evil-secret", algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_creator_id(f"Bearer {bad_token}")

    async def test_garbage_token_raises(self):
        """Completely non-JWT garbage string must raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            get_current_creator_id("Bearer this.is.garbage.data.here")

    async def test_missing_sub_claim_raises(self):
        """Token that has type=creator but no sub must raise UnauthorizedError."""
        payload = {
            "email": "nosub@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            get_current_creator_id(f"Bearer {token}")


# ===========================================================================
# keyvault.py — KeyVaultResolver
# ===========================================================================


class TestKeyVaultResolver:
    """Unit tests for KeyVaultResolver with the Azure SDK mocked out."""

    def _make_resolver(self, vault_url: str = "https://my-vault.vault.azure.net/"):
        from marketplace.core.keyvault import KeyVaultResolver
        return KeyVaultResolver(vault_url)

    # --- __init__ ---

    async def test_empty_vault_url_raises_value_error(self):
        """Constructing a resolver with an empty URL must raise ValueError."""
        from marketplace.core.keyvault import KeyVaultResolver
        with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL"):
            KeyVaultResolver("")

    async def test_valid_vault_url_stores_url(self):
        """The vault URL should be stored on the instance."""
        r = self._make_resolver("https://test.vault.azure.net/")
        assert r._vault_url == "https://test.vault.azure.net/"
        assert r._client is None

    # --- _get_client ---

    async def test_get_client_lazy_initializes_on_first_call(self):
        """_get_client must instantiate the SDK client and cache it."""
        r = self._make_resolver()
        mock_client = MagicMock()

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=MagicMock()),
            "azure.keyvault.secrets": MagicMock(SecretClient=MagicMock(return_value=mock_client)),
        }):
            client1 = r._get_client()
            client2 = r._get_client()

        assert client1 is client2         # singleton — same object both calls

    async def test_get_client_missing_azure_packages_raises_import_error(self):
        """If azure packages are absent, _get_client must raise ImportError."""
        r = self._make_resolver()

        def _bad_import(name, *args, **kwargs):
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.__import__", side_effect=_bad_import):
            with pytest.raises((ImportError, Exception)):
                r._get_client()

    # --- get_secret ---

    async def test_get_secret_returns_value_on_success(self):
        """get_secret returns the .value of the secret object from the SDK."""
        r = self._make_resolver()
        mock_secret = MagicMock()
        mock_secret.value = "super-secret-value"
        mock_client = MagicMock()
        mock_client.get_secret.return_value = mock_secret
        r._client = mock_client

        result = r.get_secret("my-secret")

        assert result == "super-secret-value"
        mock_client.get_secret.assert_called_once_with("my-secret")

    async def test_get_secret_returns_none_on_exception(self):
        """If the SDK raises, get_secret must return None and log a warning."""
        r = self._make_resolver()
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = RuntimeError("vault unreachable")
        r._client = mock_client

        result = r.get_secret("missing-secret")

        assert result is None

    # --- set_secret ---

    async def test_set_secret_returns_true_on_success(self):
        """set_secret should return True when the SDK call succeeds."""
        r = self._make_resolver()
        mock_client = MagicMock()
        r._client = mock_client

        result = r.set_secret("my-key", "my-value")

        assert result is True
        mock_client.set_secret.assert_called_once_with("my-key", "my-value")

    async def test_set_secret_returns_false_on_exception(self):
        """set_secret should return False when the SDK call raises."""
        r = self._make_resolver()
        mock_client = MagicMock()
        mock_client.set_secret.side_effect = PermissionError("access denied")
        r._client = mock_client

        result = r.set_secret("my-key", "my-value")

        assert result is False

    # --- list_secrets ---

    async def test_list_secrets_returns_names(self):
        """list_secrets should return a list of secret names from the SDK."""
        r = self._make_resolver()
        prop_a = MagicMock()
        prop_a.name = "secret-a"
        prop_b = MagicMock()
        prop_b.name = "secret-b"
        mock_props = [prop_a, prop_b]
        mock_client = MagicMock()
        mock_client.list_properties_of_secrets.return_value = iter(mock_props)
        r._client = mock_client

        names = r.list_secrets()

        assert names == ["secret-a", "secret-b"]

    async def test_list_secrets_returns_empty_list_on_exception(self):
        """list_secrets should return [] when the SDK call raises."""
        r = self._make_resolver()
        mock_client = MagicMock()
        mock_client.list_properties_of_secrets.side_effect = RuntimeError("vault down")
        r._client = mock_client

        names = r.list_secrets()

        assert names == []


# ===========================================================================
# keyvault.py — get_keyvault_resolver
# ===========================================================================


class TestGetKeyVaultResolver:
    """Tests for the module-level resolver singleton factory."""

    async def test_returns_none_when_no_vault_url_configured(self, monkeypatch):
        """Without AZURE_KEYVAULT_URL in settings, resolver must be None."""
        import marketplace.core.keyvault as kv_module

        monkeypatch.setattr(settings, "azure_keyvault_url", "", raising=False)
        # Reset the singleton so the function re-evaluates the URL
        kv_module._resolver = None

        result = kv_module.get_keyvault_resolver()
        assert result is None

    async def test_returns_resolver_when_vault_url_present(self, monkeypatch):
        """With a vault URL set, get_keyvault_resolver returns a KeyVaultResolver."""
        import marketplace.core.keyvault as kv_module

        monkeypatch.setattr(
            settings, "azure_keyvault_url",
            "https://test.vault.azure.net/",
            raising=False,
        )
        kv_module._resolver = None

        result = kv_module.get_keyvault_resolver()
        assert result is not None
        assert result._vault_url == "https://test.vault.azure.net/"

        # Cleanup singleton so later tests are not affected
        kv_module._resolver = None

    async def test_returns_same_singleton_on_repeated_calls(self, monkeypatch):
        """Calling get_keyvault_resolver twice should return the exact same object."""
        import marketplace.core.keyvault as kv_module

        monkeypatch.setattr(
            settings, "azure_keyvault_url",
            "https://singleton.vault.azure.net/",
            raising=False,
        )
        kv_module._resolver = None

        r1 = kv_module.get_keyvault_resolver()
        r2 = kv_module.get_keyvault_resolver()
        assert r1 is r2

        kv_module._resolver = None


# ===========================================================================
# keyvault.py — resolve_secrets
# ===========================================================================


class TestResolveSecrets:
    """Tests for the resolve_secrets convenience function."""

    async def test_no_vault_returns_all_none(self, monkeypatch):
        """Without a configured vault, every secret maps to None."""
        import marketplace.core.keyvault as kv_module

        monkeypatch.setattr(settings, "azure_keyvault_url", "", raising=False)
        kv_module._resolver = None

        result = kv_module.resolve_secrets(["jwt-secret-key", "db-password"])

        assert result == {"jwt-secret-key": None, "db-password": None}

    async def test_no_vault_empty_list_returns_empty_dict(self, monkeypatch):
        """Empty secret list with no vault returns an empty dict."""
        import marketplace.core.keyvault as kv_module

        monkeypatch.setattr(settings, "azure_keyvault_url", "", raising=False)
        kv_module._resolver = None

        result = kv_module.resolve_secrets([])

        assert result == {}

    async def test_with_resolver_fetches_each_secret(self, monkeypatch):
        """With a configured vault, each name is looked up via get_secret."""
        import marketplace.core.keyvault as kv_module

        mock_resolver = MagicMock()
        mock_resolver.get_secret.side_effect = lambda name: f"value-for-{name}"

        with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
            result = kv_module.resolve_secrets(["secret-a", "secret-b"])

        assert result == {"secret-a": "value-for-secret-a", "secret-b": "value-for-secret-b"}

    async def test_partial_failure_returns_none_for_missing(self, monkeypatch):
        """When one secret is missing (get_secret returns None), that key maps to None."""
        import marketplace.core.keyvault as kv_module

        def _lookup(name: str):
            return "found" if name == "existing-secret" else None

        mock_resolver = MagicMock()
        mock_resolver.get_secret.side_effect = _lookup

        with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
            result = kv_module.resolve_secrets(["existing-secret", "missing-secret"])

        assert result["existing-secret"] == "found"
        assert result["missing-secret"] is None


# ===========================================================================
# keyvault.py — resolve_and_override_settings
# ===========================================================================


class TestResolveAndOverrideSettings:
    """Tests for the startup settings-override function."""

    async def test_no_resolver_returns_early_without_touching_settings(self, monkeypatch):
        """When no vault is configured, settings are not modified."""
        import marketplace.core.keyvault as kv_module

        original_jwt = settings.jwt_secret_key

        with patch.object(kv_module, "get_keyvault_resolver", return_value=None):
            kv_module.resolve_and_override_settings()

        assert settings.jwt_secret_key == original_jwt

    async def test_secrets_override_settings_attributes(self, monkeypatch):
        """Each resolved secret value should be written to the matching settings attr."""
        import marketplace.core.keyvault as kv_module

        mock_resolver = MagicMock()
        mock_resolver.get_secret.side_effect = lambda name: (
            "new-jwt-secret" if name == "jwt-secret-key" else None
        )

        with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
            kv_module.resolve_and_override_settings()

        assert settings.jwt_secret_key == "new-jwt-secret"

        # Restore so other tests are not broken
        monkeypatch.setattr(settings, "jwt_secret_key", "test-secret-key-for-dev-only", raising=False)

    async def test_none_value_secrets_are_not_written(self, monkeypatch):
        """Secrets that return None must NOT overwrite existing settings values."""
        import marketplace.core.keyvault as kv_module

        original = settings.jwt_secret_key
        mock_resolver = MagicMock()
        mock_resolver.get_secret.return_value = None   # all secrets missing

        with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
            kv_module.resolve_and_override_settings()

        assert settings.jwt_secret_key == original

    async def test_database_password_key_is_skipped(self, monkeypatch):
        """'database-password' is mapped to None and must not cause setattr errors."""
        import marketplace.core.keyvault as kv_module

        calls: list[str] = []

        def _lookup(name: str):
            calls.append(name)
            return "some-value"

        mock_resolver = MagicMock()
        mock_resolver.get_secret.side_effect = _lookup

        # This call must not raise even though database-password -> None mapping exists
        with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
            kv_module.resolve_and_override_settings()

        # database-password maps to None in _KV_SETTINGS_MAP so get_secret is
        # never called for it — the loop skips it via `if not settings_attr: continue`
        assert "database-password" not in calls

    async def test_resolved_count_logged(self, monkeypatch, caplog):
        """When secrets are resolved, an INFO log with the count is emitted."""
        import marketplace.core.keyvault as kv_module

        mock_resolver = MagicMock()
        mock_resolver.get_secret.side_effect = lambda name: "v"

        with caplog.at_level(logging.INFO, logger="marketplace.core.keyvault"):
            with patch.object(kv_module, "get_keyvault_resolver", return_value=mock_resolver):
                kv_module.resolve_and_override_settings()

        assert "Resolved" in caplog.text
        assert "secrets from Key Vault" in caplog.text
