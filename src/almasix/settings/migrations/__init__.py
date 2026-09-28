"""Settings property migrations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from almasix.settings.crypto import decrypt_payload, encrypt_payload, try_decrypt_payload
from almasix.settings.repository import get_repository
from almasix.settings.tenant import GLOBAL_TENANT_ID


class SettingsBlueprint:
    """Fluent builder used inside ``migrator.in_group(...)``."""

    def __init__(self, migrator: SettingsMigrator, group: str, *, tenant_id: str) -> None:
        self.migrator = migrator
        self.group = group
        self.tenant_id = tenant_id
        self._ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def add(self, name: str, payload: Any, *, locked: bool = False) -> SettingsBlueprint:
        self._ops.append(("add", (name, payload), {"locked": locked, "encrypted": False}))
        return self

    def add_encrypted(self, name: str, payload: Any, *, locked: bool = False) -> SettingsBlueprint:
        self._ops.append(("add", (name, payload), {"locked": locked, "encrypted": True}))
        return self

    def update(self, name: str, payload: Any) -> SettingsBlueprint:
        self._ops.append(("update", (name, payload), {"encrypted": False}))
        return self

    def update_encrypted(self, name: str, payload: Any) -> SettingsBlueprint:
        self._ops.append(("update", (name, payload), {"encrypted": True}))
        return self

    def rename(self, old: str, new: str) -> SettingsBlueprint:
        self._ops.append(("rename", (old, new), {}))
        return self

    def delete(self, name: str) -> SettingsBlueprint:
        self._ops.append(("delete", (name,), {}))
        return self

    def encrypt(self, name: str) -> SettingsBlueprint:
        self._ops.append(("encrypt", (name,), {}))
        return self

    def decrypt(self, name: str) -> SettingsBlueprint:
        self._ops.append(("decrypt", (name,), {}))
        return self

    def lock(self, *names: str) -> SettingsBlueprint:
        self._ops.append(("lock", names, {}))
        return self

    def unlock(self, *names: str) -> SettingsBlueprint:
        self._ops.append(("unlock", names, {}))
        return self

    def run(self) -> None:
        for op, args, kwargs in self._ops:
            getattr(self.migrator, f"_op_{op}")(self.group, *args, tenant_id=self.tenant_id, **kwargs)


class SettingsMigrator:
    """Applies property-level settings migrations against a repository."""

    def __init__(self, repository_name: str | None = None) -> None:
        self.repository_name = repository_name

    def repo(self) -> Any:
        return get_repository(self.repository_name)

    def in_group(
        self,
        group: str,
        callback: Callable[[SettingsBlueprint], Any] | None = None,
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> SettingsBlueprint:
        blueprint = SettingsBlueprint(self, group, tenant_id=tenant_id)
        if callback is not None:
            callback(blueprint)
            blueprint.run()
        return blueprint

    def _op_add(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        tenant_id: str,
        locked: bool = False,
        encrypted: bool = False,
    ) -> None:
        repo = self.repo()
        if repo.check_if_property_exists(group, name, tenant_id=tenant_id):
            return
        store = encrypt_payload(payload) if encrypted else payload
        repo.create_property(group, name, store, locked=locked, tenant_id=tenant_id)

    def _op_update(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        tenant_id: str,
        encrypted: bool = False,
    ) -> None:
        repo = self.repo()
        store = encrypt_payload(payload) if encrypted else payload
        if not repo.check_if_property_exists(group, name, tenant_id=tenant_id):
            repo.create_property(group, name, store, tenant_id=tenant_id)
        else:
            repo.update_properties_payload(group, {name: store}, tenant_id=tenant_id)

    def _op_rename(self, group: str, old: str, new: str, *, tenant_id: str) -> None:
        repo = self.repo()
        if not repo.check_if_property_exists(group, old, tenant_id=tenant_id):
            return
        payload = repo.get_property_payload(group, old, tenant_id=tenant_id)
        locked = old in repo.get_locked_properties(group, tenant_id=tenant_id)
        if not repo.check_if_property_exists(group, new, tenant_id=tenant_id):
            repo.create_property(group, new, payload, locked=locked, tenant_id=tenant_id)
        repo.delete_property(group, old, tenant_id=tenant_id)

    def _op_delete(self, group: str, name: str, *, tenant_id: str) -> None:
        self.repo().delete_property(group, name, tenant_id=tenant_id)

    def _op_encrypt(self, group: str, name: str, *, tenant_id: str) -> None:
        repo = self.repo()
        if not repo.check_if_property_exists(group, name, tenant_id=tenant_id):
            return
        payload = repo.get_property_payload(group, name, tenant_id=tenant_id)
        # Avoid double-encrypt: if decrypt works and re-encrypt differs, assume plaintext.
        plain = try_decrypt_payload(payload)
        # If decrypt returned something different-looking ciphertext still, encrypt plain.
        repo.update_properties_payload(
            group, {name: encrypt_payload(plain)}, tenant_id=tenant_id
        )

    def _op_decrypt(self, group: str, name: str, *, tenant_id: str) -> None:
        repo = self.repo()
        if not repo.check_if_property_exists(group, name, tenant_id=tenant_id):
            return
        payload = repo.get_property_payload(group, name, tenant_id=tenant_id)
        try:
            plain = decrypt_payload(payload)
        except Exception:
            plain = payload
        repo.update_properties_payload(group, {name: plain}, tenant_id=tenant_id)

    def _op_lock(self, group: str, *names: str, tenant_id: str) -> None:
        self.repo().lock_properties(group, names, tenant_id=tenant_id)

    def _op_unlock(self, group: str, *names: str, tenant_id: str) -> None:
        self.repo().unlock_properties(group, names, tenant_id=tenant_id)


class SettingsMigration:
    """Base class for settings property migrations under ``database/settings/``."""

    def __init__(self) -> None:
        self.migrator = SettingsMigrator()

    async def up(self) -> None:  # pragma: no cover - subclasses implement
        raise NotImplementedError

    async def down(self) -> None:  # pragma: no cover - optional
        pass


__all__ = [
    "SettingsBlueprint",
    "SettingsMigration",
    "SettingsMigrator",
]
