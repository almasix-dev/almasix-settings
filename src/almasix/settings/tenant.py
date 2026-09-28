"""Tenant context for scoped settings."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

# Empty string = global (works with unique (group, name, tenant_id) on all DBs).
GLOBAL_TENANT_ID = ""

_tenant_id: ContextVar[str | None] = ContextVar("almasix_settings_tenant_id", default=None)
_tenant_resolver: Callable[[], str | None] | None = None


def normalize_tenant_id(tenant: Any = None) -> str:
    """Coerce a tenant object / id / slug into a storage key.

    ``None`` / missing → global (``""``).
    """
    if tenant is None:
        return GLOBAL_TENANT_ID
    if isinstance(tenant, str):
        return tenant.strip()
    tid = getattr(tenant, "id", None)
    if tid is not None and str(tid).strip():
        return str(tid).strip()
    slug = getattr(tenant, "slug", None)
    if slug is not None and str(slug).strip():
        return str(slug).strip()
    return str(tenant).strip() or GLOBAL_TENANT_ID


def set_tenant_resolver(resolver: Callable[[], str | None] | None) -> None:
    """Install a callable that returns the current tenant id (Orbit binds this)."""
    global _tenant_resolver
    _tenant_resolver = resolver


def get_tenant_resolver() -> Callable[[], str | None] | None:
    return _tenant_resolver


def set_current_tenant(tenant: Any = None) -> None:
    """Pin the current tenant for this context (tests / explicit scopes)."""
    if tenant is None:
        _tenant_id.set(None)
    else:
        _tenant_id.set(normalize_tenant_id(tenant))


def clear_current_tenant() -> None:
    _tenant_id.set(None)


def current_tenant_id(*, explicit: Any = ..., scoped: bool = True) -> str:
    """Resolve the tenant key used for load/save.

    When ``scoped`` is False, always returns the global key.
    ``explicit`` overrides resolver/context when not the sentinel ``...``.
    """
    if not scoped:
        return GLOBAL_TENANT_ID
    if explicit is not ...:
        return normalize_tenant_id(explicit)
    pinned = _tenant_id.get()
    if pinned is not None:
        return pinned
    resolver = _tenant_resolver
    if resolver is not None:
        try:
            return normalize_tenant_id(resolver())
        except Exception:
            return GLOBAL_TENANT_ID
    return GLOBAL_TENANT_ID
