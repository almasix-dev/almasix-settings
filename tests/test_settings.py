"""Tests for almasix.settings."""

from __future__ import annotations

import pytest
from almasix.encryption.encrypter import Encrypter
from almasix.encryption.facade import Crypt

from almasix.settings import (
    GLOBAL_TENANT_ID,
    Settings,
    SettingsMigrator,
    SettingsPropertyLocked,
    bootstrap_default_repositories,
    clear_current_tenant,
    get_repository,
    normalize_tenant_id,
    register_repository,
    set_current_tenant,
    set_default_repository,
    set_tenant_resolver,
)
from almasix.settings.migrator_runner import reset_applied_migrations, run_settings_migrations
from almasix.settings.repositories.memory import MemorySettingsRepository


@pytest.fixture(autouse=True)
def _fresh_repo() -> None:
    bootstrap_default_repositories()
    mem = MemorySettingsRepository()
    register_repository("memory", mem)
    set_default_repository("memory")
    clear_current_tenant()
    set_tenant_resolver(None)
    Crypt.set_encrypter(Encrypter("settings-test-key"))
    reset_applied_migrations()
    yield
    clear_current_tenant()
    set_tenant_resolver(None)
    Crypt.set_encrypter(None)


class GeneralSettings(Settings):
    site_name: str
    site_active: bool
    api_token: str

    @classmethod
    def group(cls) -> str:
        return "general"

    @classmethod
    def encrypted(cls) -> tuple[str, ...]:
        return ("api_token",)


class TenantMailSettings(Settings):
    tenant_scoped = True

    from_address: str
    reply_to: str

    @classmethod
    def group(cls) -> str:
        return "mail"


def test_normalize_tenant_id() -> None:
    assert normalize_tenant_id(None) == GLOBAL_TENANT_ID
    assert normalize_tenant_id(" acme ") == "acme"
    assert normalize_tenant_id(type("T", (), {"id": 7})()) == "7"
    assert normalize_tenant_id(type("T", (), {"slug": "beta", "id": None})()) == "beta"


def test_memory_load_save_and_encryption() -> None:
    migrator = SettingsMigrator()
    migrator.in_group(
        "general",
        lambda b: (
            b.add("site_name", "Orbit"),
            b.add("site_active", True),
            b.add_encrypted("api_token", "secret"),
        ),
    )
    settings = GeneralSettings.load()
    assert settings.site_name == "Orbit"
    assert settings.site_active is True
    assert settings.api_token == "secret"
    # Stored ciphertext is not plaintext.
    raw = get_repository().get_property_payload("general", "api_token")
    assert raw != "secret"
    settings.site_name = "Acme"
    settings.api_token = "rotated"
    settings.save()
    again = GeneralSettings.load()
    assert again.site_name == "Acme"
    assert again.api_token == "rotated"
    assert again.to_dict()["site_name"] == "Acme"


def test_locked_property_skipped_on_save_and_fill() -> None:
    migrator = SettingsMigrator()
    migrator.in_group(
        "general",
        lambda b: (
            b.add("site_name", "Orbit", locked=True),
            b.add("site_active", True),
            b.add_encrypted("api_token", ""),
        ),
    )
    settings = GeneralSettings.load()
    settings.site_name = "Hacked"
    settings.site_active = False
    settings.save()
    reloaded = GeneralSettings.load()
    assert reloaded.site_name == "Orbit"
    assert reloaded.site_active is False
    with pytest.raises(SettingsPropertyLocked):
        reloaded.fill({"site_name": "Nope"})


def test_tenant_scoped_isolation_and_global_fallback() -> None:
    migrator = SettingsMigrator()
    migrator.in_group(
        "mail",
        lambda b: (
            b.add("from_address", "hello@global.test"),
            b.add("reply_to", "noreply@global.test"),
        ),
    )
    # No tenant → global values via fallback.
    set_current_tenant("acme")
    mail = TenantMailSettings.load()
    assert mail.from_address == "hello@global.test"
    mail.from_address = "team@acme.test"
    mail.save()
    set_current_tenant("beta")
    other = TenantMailSettings.load()
    assert other.from_address == "hello@global.test"
    set_current_tenant("acme")
    assert TenantMailSettings.load().from_address == "team@acme.test"


def test_tenant_resolver_callable() -> None:
    migrator = SettingsMigrator()
    migrator.in_group(
        "mail",
        lambda b: (b.add("from_address", "g@t"), b.add("reply_to", "r@t")),
    )
    set_tenant_resolver(lambda: "tenant-9")
    mail = TenantMailSettings.load()
    mail.from_address = "nine@t"
    mail.save()
    set_tenant_resolver(lambda: "tenant-9")
    assert TenantMailSettings.load().from_address == "nine@t"
    set_tenant_resolver(lambda: "other")
    assert TenantMailSettings.load().from_address == "g@t"


def test_migrator_rename_delete_lock_encrypt_decrypt(tmp_path) -> None:
    migrator = SettingsMigrator()
    migrator.in_group(
        "general",
        lambda b: (
            b.add("site_name", "Orbit"),
            b.add("old_flag", True),
            b.add("plain_secret", "x"),
        ),
    )
    migrator.in_group(
        "general",
        lambda b: (
            b.rename("old_flag", "site_active"),
            b.delete("missing"),
            b.encrypt("plain_secret"),
            b.lock("site_name"),
        ),
    )
    repo = get_repository()
    assert repo.check_if_property_exists("general", "site_active")
    assert not repo.check_if_property_exists("general", "old_flag")
    assert "site_name" in repo.get_locked_properties("general")
    cipher = repo.get_property_payload("general", "plain_secret")
    assert cipher != "x"
    migrator.in_group("general", lambda b: (b.decrypt("plain_secret"), b.unlock("site_name")))
    assert repo.get_property_payload("general", "plain_secret") == "x"
    assert "site_name" not in repo.get_locked_properties("general")

    # Runner discovers files.
    folder = tmp_path / "database" / "settings"
    folder.mkdir(parents=True)
    (folder / "2026_01_01_000000_seed.py").write_text(
        "from almasix.settings.migrations import SettingsMigration\n"
        "class Seed(SettingsMigration):\n"
        "    async def up(self):\n"
        "        self.migrator.in_group('runner', lambda b: b.add('ok', True))\n",
        encoding="utf-8",
    )
    assert run_settings_migrations(base_path=tmp_path) == 1
    assert get_repository().check_if_property_exists("runner", "ok")
    assert run_settings_migrations(base_path=tmp_path) == 0


def test_redis_repository_round_trip(monkeypatch) -> None:
    from almasix.settings.repositories import redis as redis_mod

    store: dict[str, str] = {}

    class FakeRedis:
        @classmethod
        def connection(cls, name=None):
            return cls

        @classmethod
        def get(cls, key, *, connection=None):
            val = store.get(key)
            return None if val is None else val.encode()

        @classmethod
        def set(cls, key, value, *, ex=None, connection=None):
            store[key] = value if isinstance(value, str) else str(value)
            return True

        @classmethod
        def delete(cls, *keys, connection=None):
            for k in keys:
                store.pop(k, None)
            return len(keys)

    class AsyncClient:
        async def scan_iter(self, match=None):
            for key in list(store):
                if match and match.endswith(":*"):
                    prefix = match[:-1]
                    if key.startswith(prefix):
                        yield key.encode()
                elif match is None or key == match:
                    yield key.encode()

        async def get(self, key):
            val = store.get(key.decode() if isinstance(key, bytes) else key)
            return None if val is None else val.encode()

    client = AsyncClient()

    class Facade:
        @classmethod
        def connection(cls, name=None):
            return client

        @classmethod
        def get(cls, key, *, connection=None):
            return FakeRedis.get(key, connection=connection)

        @classmethod
        def set(cls, key, value, *, ex=None, connection=None):
            return FakeRedis.set(key, value, ex=ex, connection=connection)

        @classmethod
        def delete(cls, *keys, connection=None):
            return FakeRedis.delete(*keys, connection=connection)

    monkeypatch.setattr(redis_mod, "_require_redis", lambda: None)
    repo = redis_mod.RedisSettingsRepository(prefix="t")
    monkeypatch.setattr(repo, "_client", lambda: Facade)

    repo.create_property("g", "a", {"n": 1}, locked=False)
    assert repo.check_if_property_exists("g", "a")
    assert repo.get_property_payload("g", "a") == {"n": 1}
    repo.update_properties_payload("g", {"a": {"n": 2}})
    assert repo.get_property_payload("g", "a") == {"n": 2}
    repo.lock_properties("g", ["a"])
    assert "a" in repo.get_locked_properties("g")
    repo.unlock_properties("g", ["a"])
    assert "a" not in repo.get_locked_properties("g")
    props = repo.get_properties_in_group("g")
    assert props["a"] == {"n": 2}
    repo.delete_property("g", "a")
    assert not repo.check_if_property_exists("g", "a")


def test_missing_redis_extra(monkeypatch) -> None:
    import builtins

    from almasix.settings.exceptions import MissingRedisExtra
    from almasix.settings.repositories import redis as redis_mod

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis" or name.startswith("redis."):
            raise ImportError("no redis")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(MissingRedisExtra):
        redis_mod._require_redis()
