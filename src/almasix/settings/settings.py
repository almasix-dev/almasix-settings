"""Typed Settings base class."""

from __future__ import annotations

from typing import Any, ClassVar, Self, get_type_hints

from almasix.settings.crypto import encrypt_payload, try_decrypt_payload
from almasix.settings.exceptions import MissingSettings, SettingsPropertyLocked
from almasix.settings.repository import get_repository
from almasix.settings.tenant import GLOBAL_TENANT_ID, current_tenant_id


class Settings:
    """Typed settings bag persisted through a :class:`SettingsRepository`.

    Subclass, declare public typed attributes, and implement :meth:`group`.
    """

    tenant_scoped: ClassVar[bool] = False
    repository_name: ClassVar[str | None] = None

    _loaded: bool
    _tenant_id: str
    _original: dict[str, Any]

    def __init__(self, **values: Any) -> None:
        object.__setattr__(self, "_loaded", False)
        object.__setattr__(self, "_tenant_id", GLOBAL_TENANT_ID)
        object.__setattr__(self, "_original", {})
        for name in type(self).property_names():
            if name in values:
                object.__setattr__(self, name, values[name])

    @classmethod
    def group(cls) -> str:
        raise NotImplementedError(f"{cls.__name__}.group() must return a settings group name")

    @classmethod
    def encrypted(cls) -> tuple[str, ...]:
        return ()

    @classmethod
    def is_tenant_scoped(cls) -> bool:
        return bool(getattr(cls, "tenant_scoped", False))

    @classmethod
    def repository(cls) -> str | None:
        return cls.repository_name

    @classmethod
    def casts(cls) -> dict[str, Any]:
        return {}

    @classmethod
    def property_names(cls) -> list[str]:
        hints = get_type_hints(cls)
        skip = {
            "tenant_scoped",
            "repository_name",
            "_loaded",
            "_tenant_id",
            "_original",
        }
        return [name for name in hints if not name.startswith("_") and name not in skip]

    @classmethod
    def load(cls, tenant: Any = ...) -> Self:
        """Load settings for the current (or explicit) tenant."""
        instance = cls()
        instance.refresh(tenant=tenant)
        return instance

    def refresh(self, tenant: Any = ...) -> Self:
        tid = current_tenant_id(explicit=tenant, scoped=type(self).is_tenant_scoped())
        object.__setattr__(self, "_tenant_id", tid)
        repo = get_repository(type(self).repository())
        group = type(self).group()
        stored = repo.get_properties_in_group(group, tenant_id=tid)
        # Fall back to global defaults for tenant-scoped classes with no row yet.
        if type(self).is_tenant_scoped() and tid != GLOBAL_TENANT_ID:
            global_stored = repo.get_properties_in_group(group, tenant_id=GLOBAL_TENANT_ID)
            for key, value in global_stored.items():
                stored.setdefault(key, value)
        encrypted = set(type(self).encrypted())
        original: dict[str, Any] = {}
        for name in type(self).property_names():
            if name not in stored:
                # Leave unset attributes alone if already set; otherwise MissingSettings on access.
                continue
            value = stored[name]
            if name in encrypted:
                value = try_decrypt_payload(value)
            object.__setattr__(self, name, value)
            original[name] = value
        object.__setattr__(self, "_original", original)
        object.__setattr__(self, "_loaded", True)
        return self

    def get(self, name: str, default: Any = ...) -> Any:
        if hasattr(self, name):
            return getattr(self, name)
        if default is not ...:
            return default
        raise MissingSettings(f"{type(self).__name__}.{name} is not set")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in type(self).property_names():
            if hasattr(self, name):
                out[name] = getattr(self, name)
        return out

    def save(self) -> Self:
        repo = get_repository(type(self).repository())
        group = type(self).group()
        tid = getattr(self, "_tenant_id", GLOBAL_TENANT_ID)
        locked = set(repo.get_locked_properties(group, tenant_id=tid))
        # Locked set may live only on global rows for brand-new tenants.
        if type(self).is_tenant_scoped() and tid != GLOBAL_TENANT_ID:
            locked |= set(repo.get_locked_properties(group, tenant_id=GLOBAL_TENANT_ID))
        encrypted = set(type(self).encrypted())
        updates: dict[str, Any] = {}
        for name in type(self).property_names():
            if name not in self.__dict__ and not hasattr(self, name):
                continue
            if name in locked:
                continue
            value = getattr(self, name)
            store_value = encrypt_payload(value) if name in encrypted else value
            updates[name] = store_value
        if updates:
            # Ensure properties exist before update (create missing).
            for name, payload in updates.items():
                if not repo.check_if_property_exists(group, name, tenant_id=tid):
                    repo.create_property(group, name, payload, tenant_id=tid)
            repo.update_properties_payload(group, updates, tenant_id=tid)
        object.__setattr__(self, "_original", self.to_dict())
        object.__setattr__(self, "_loaded", True)
        return self

    def lock(self, *names: str) -> Self:
        repo = get_repository(type(self).repository())
        tid = getattr(self, "_tenant_id", GLOBAL_TENANT_ID)
        repo.lock_properties(type(self).group(), names, tenant_id=tid)
        return self

    def unlock(self, *names: str) -> Self:
        repo = get_repository(type(self).repository())
        tid = getattr(self, "_tenant_id", GLOBAL_TENANT_ID)
        repo.unlock_properties(type(self).group(), names, tenant_id=tid)
        return self

    def fill(self, data: dict[str, Any], *, respect_locked: bool = True) -> Self:
        """Assign attributes from a form payload."""
        repo = get_repository(type(self).repository())
        tid = getattr(self, "_tenant_id", GLOBAL_TENANT_ID)
        locked = (
            set(repo.get_locked_properties(type(self).group(), tenant_id=tid))
            if respect_locked
            else set()
        )
        for name, value in data.items():
            if name not in type(self).property_names():
                continue
            if name in locked:
                raise SettingsPropertyLocked(f"{type(self).__name__}.{name} is locked")
            setattr(self, name, value)
        return self
