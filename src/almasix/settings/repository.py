"""Settings repository protocol and factory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from almasix.settings.exceptions import UnknownRepository
from almasix.settings.tenant import GLOBAL_TENANT_ID


@runtime_checkable
class SettingsRepository(Protocol):
    """Persist settings properties keyed by group + name + tenant."""

    def get_properties_in_group(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> dict[str, Any]: ...

    def check_if_property_exists(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> bool: ...

    def get_property_payload(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> Any: ...

    def create_property(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        locked: bool = False,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None: ...

    def update_properties_payload(
        self,
        group: str,
        properties: Mapping[str, Any],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None: ...

    def delete_property(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> None: ...

    def lock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None: ...

    def unlock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None: ...

    def get_locked_properties(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> list[str]: ...


_repositories: dict[str, SettingsRepository] = {}
_default_name: str = "memory"


def set_default_repository(name: str) -> None:
    global _default_name
    _default_name = name


def get_default_repository_name() -> str:
    return _default_name


def register_repository(name: str, repository: SettingsRepository) -> None:
    _repositories[name] = repository


def get_repository(name: str | None = None) -> SettingsRepository:
    key = name or _default_name
    if key not in _repositories:
        raise UnknownRepository(
            f"Settings repository {key!r} is not registered. Known: {sorted(_repositories)!r}"
        )
    return _repositories[key]


def clear_repositories() -> None:
    """Reset registry (tests)."""
    _repositories.clear()
    global _default_name
    _default_name = "memory"


def bootstrap_default_repositories() -> None:
    """Register memory + database (+ redis when importable). Safe to call repeatedly."""
    from almasix.settings.repositories.memory import MemorySettingsRepository

    if "memory" not in _repositories:
        register_repository("memory", MemorySettingsRepository())
    if "database" not in _repositories:
        from almasix.settings.repositories.database import DatabaseSettingsRepository

        register_repository("database", DatabaseSettingsRepository())
    try:
        from almasix.settings.repositories.redis import RedisSettingsRepository

        if "redis" not in _repositories:
            register_repository("redis", RedisSettingsRepository())
    except Exception:
        pass
    if "memory" in _repositories and _default_name not in _repositories:
        set_default_repository("memory")
