"""In-memory settings repository (tests and demos)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from almasix.settings.tenant import GLOBAL_TENANT_ID


class MemorySettingsRepository:
    """Dict-backed repository — no database required."""

    def __init__(self) -> None:
        # (tenant_id, group, name) -> {"payload": Any, "locked": bool}
        self._rows: dict[tuple[str, str, str], dict[str, Any]] = {}

    def clear(self) -> None:
        self._rows.clear()

    def get_properties_in_group(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for (tid, grp, name), row in self._rows.items():
            if tid == tenant_id and grp == group:
                out[name] = deepcopy(row["payload"])
        return out

    def check_if_property_exists(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> bool:
        return (tenant_id, group, name) in self._rows

    def get_property_payload(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> Any:
        row = self._rows.get((tenant_id, group, name))
        if row is None:
            return None
        return deepcopy(row["payload"])

    def create_property(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        locked: bool = False,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        self._rows[(tenant_id, group, name)] = {
            "payload": deepcopy(payload),
            "locked": bool(locked),
        }

    def update_properties_payload(
        self,
        group: str,
        properties: Mapping[str, Any],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name, payload in properties.items():
            key = (tenant_id, group, name)
            if key in self._rows:
                self._rows[key]["payload"] = deepcopy(payload)
            else:
                self.create_property(group, name, payload, tenant_id=tenant_id)

    def delete_property(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> None:
        self._rows.pop((tenant_id, group, name), None)

    def lock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name in properties:
            key = (tenant_id, group, name)
            if key in self._rows:
                self._rows[key]["locked"] = True

    def unlock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name in properties:
            key = (tenant_id, group, name)
            if key in self._rows:
                self._rows[key]["locked"] = False

    def get_locked_properties(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> list[str]:
        return sorted(
            name
            for (tid, grp, name), row in self._rows.items()
            if tid == tenant_id and grp == group and row.get("locked")
        )
