"""Extra coverage for settings edge paths."""

from __future__ import annotations

from typing import Any

import pytest
from almasix.encryption.encrypter import Encrypter
from almasix.encryption.facade import Crypt

from almasix.settings import (
    Settings,
    UnknownRepository,
    bootstrap_default_repositories,
    clear_current_tenant,
    current_tenant_id,
    get_repository,
    register_repository,
    set_current_tenant,
    set_default_repository,
    set_tenant_resolver,
)
from almasix.settings.crypto import try_decrypt_payload
from almasix.settings.exceptions import MissingSettings
from almasix.settings.migrations import SettingsMigrator
from almasix.settings.repositories.memory import MemorySettingsRepository
from almasix.settings.repository import (
    clear_repositories,
    get_default_repository_name,
)
from almasix.settings.tenant import normalize_tenant_id


@pytest.fixture(autouse=True)
def _fresh() -> None:
    clear_repositories()
    bootstrap_default_repositories()
    mem = MemorySettingsRepository()
    register_repository("memory", mem)
    set_default_repository("memory")
    clear_current_tenant()
    set_tenant_resolver(None)
    Crypt.set_encrypter(Encrypter("cov-key"))
    yield
    Crypt.set_encrypter(None)
    clear_current_tenant()


class FlagSettings(Settings):
    enabled: bool
    label: str

    @classmethod
    def group(cls) -> str:
        return "flags"


def test_unknown_repository() -> None:
    with pytest.raises(UnknownRepository):
        get_repository("nope")


def test_settings_get_and_missing() -> None:
    SettingsMigrator().in_group("flags", lambda b: (b.add("enabled", True), b.add("label", "x")))
    s = FlagSettings.load()
    assert s.get("label") == "x"
    assert s.get("missing", "d") == "d"
    with pytest.raises(MissingSettings):
        s.get("missing")


def test_lock_unlock_helpers() -> None:
    SettingsMigrator().in_group("flags", lambda b: (b.add("enabled", True), b.add("label", "x")))
    s = FlagSettings.load()
    s.lock("label")
    assert "label" in get_repository().get_locked_properties("flags")
    s.unlock("label")
    assert "label" not in get_repository().get_locked_properties("flags")


def test_explicit_tenant_override_and_clear() -> None:
    class T(Settings):
        tenant_scoped = True
        value: str

        @classmethod
        def group(cls) -> str:
            return "t"

    SettingsMigrator().in_group("t", lambda b: b.add("value", "global"))
    set_current_tenant("one")
    a = T.load()
    a.value = "one-val"
    a.save()
    b = T.load(tenant="two")
    assert b.value == "global"
    b.value = "two-val"
    b.save()
    assert T.load(tenant="one").value == "one-val"
    assert T.load(tenant="two").value == "two-val"
    clear_current_tenant()
    assert current_tenant_id(scoped=False) == ""


def test_tenant_resolver_exception_falls_back() -> None:
    def boom() -> str:
        raise RuntimeError("nope")

    set_tenant_resolver(boom)
    assert current_tenant_id(scoped=True) == ""


def test_normalize_string_tenant_and_str_fallback() -> None:
    assert normalize_tenant_id(123) == "123"


def test_try_decrypt_invalid() -> None:
    assert try_decrypt_payload("not-cipher") == "not-cipher"
    assert try_decrypt_payload(None) is None


def test_memory_clear_and_update_create() -> None:
    repo = MemorySettingsRepository()
    repo.create_property("g", "a", 1)
    repo.update_properties_payload("g", {"b": 2})
    assert repo.get_property_payload("g", "b") == 2
    assert repo.get_property_payload("g", "missing") is None
    repo.clear()
    assert repo.get_properties_in_group("g") == {}


def test_casts_and_group_not_implemented() -> None:
    assert FlagSettings.casts() == {}

    class Bad(Settings):
        x: int

    with pytest.raises(NotImplementedError):
        Bad.group()


def test_fill_unlocked() -> None:
    SettingsMigrator().in_group("flags", lambda b: (b.add("enabled", False), b.add("label", "a")))
    s = FlagSettings.load()
    s.fill({"enabled": True, "label": "b", "ignored": 1})
    s.save()
    assert FlagSettings.load().enabled is True
    assert FlagSettings.load().label == "b"


def test_default_repository_name() -> None:
    assert get_default_repository_name() == "memory"


def test_database_repository_with_fake_qb(monkeypatch) -> None:
    from almasix.settings.repositories.database import DatabaseSettingsRepository

    rows: list[dict[str, Any]] = []

    class FakeQB:
        def __init__(self) -> None:
            self._wheres: list[tuple[str, Any]] = []

        def where(self, col: str, val: Any) -> FakeQB:
            self._wheres.append((col, val))
            return self

        async def get(self) -> list[dict[str, Any]]:
            return [r for r in rows if self._match(r)]

        async def first(self) -> dict[str, Any] | None:
            matched = [r for r in rows if self._match(r)]
            return matched[0] if matched else None

        async def insert(self, data: dict[str, Any]) -> None:
            rows.append(dict(data))

        async def update(self, data: dict[str, Any]) -> None:
            for r in rows:
                if self._match(r):
                    r.update(data)

        async def delete(self) -> None:
            keep = [r for r in rows if not self._match(r)]
            rows.clear()
            rows.extend(keep)

        def _match(self, r: dict[str, Any]) -> bool:
            return all(r.get(c) == v for c, v in self._wheres)

    repo = DatabaseSettingsRepository(table="settings")
    monkeypatch.setattr(repo, "_qb", FakeQB)
    repo.create_property("g", "n", {"x": 1})
    assert repo.check_if_property_exists("g", "n")
    assert repo.get_property_payload("g", "n") == {"x": 1}
    assert repo.get_properties_in_group("g")["n"] == {"x": 1}
    repo.update_properties_payload("g", {"n": {"x": 2}, "m": 3})
    assert repo.get_property_payload("g", "n") == {"x": 2}
    assert repo.get_property_payload("g", "m") == 3
    repo.lock_properties("g", ["n"])
    assert "n" in repo.get_locked_properties("g")
    repo.unlock_properties("g", ["n"])
    assert "n" not in repo.get_locked_properties("g")
    repo.delete_property("g", "m")
    assert not repo.check_if_property_exists("g", "m")
