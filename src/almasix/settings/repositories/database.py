"""Database-backed settings repository (default production store)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from almasix.settings.tenant import GLOBAL_TENANT_ID


def _run(coro: Any) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _encode(payload: Any) -> str:
    return json.dumps(payload)


def _decode(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    text = str(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return raw


class DatabaseSettingsRepository:
    """Persist settings rows in the ``settings`` table via Almasix ``DB``."""

    def __init__(self, *, table: str = "settings", connection: str | None = None) -> None:
        self.table = table
        self.connection = connection

    def _qb(self) -> Any:
        from almasix.orm.facade import DB

        return DB.table(self.table, connection=self.connection)

    def get_properties_in_group(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> dict[str, Any]:
        async def _load() -> dict[str, Any]:
            rows = await (
                self._qb()
                .where("group", group)
                .where("tenant_id", tenant_id)
                .get()
            )
            return {str(r["name"]): _decode(r.get("payload")) for r in rows}

        return _run(_load())

    def check_if_property_exists(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> bool:
        async def _exists() -> bool:
            row = await (
                self._qb()
                .where("group", group)
                .where("name", name)
                .where("tenant_id", tenant_id)
                .first()
            )
            return row is not None

        return bool(_run(_exists()))

    def get_property_payload(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> Any:
        async def _get() -> Any:
            row = await (
                self._qb()
                .where("group", group)
                .where("name", name)
                .where("tenant_id", tenant_id)
                .first()
            )
            if row is None:
                return None
            return _decode(row.get("payload"))

        return _run(_get())

    def create_property(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        locked: bool = False,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        async def _create() -> None:
            await self._qb().insert(
                {
                    "group": group,
                    "name": name,
                    "tenant_id": tenant_id,
                    "locked": bool(locked),
                    "payload": _encode(payload),
                }
            )

        _run(_create())

    def update_properties_payload(
        self,
        group: str,
        properties: Mapping[str, Any],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        async def _update() -> None:
            for name, payload in properties.items():
                existing = await (
                    self._qb()
                    .where("group", group)
                    .where("name", name)
                    .where("tenant_id", tenant_id)
                    .first()
                )
                if existing is None:
                    await self._qb().insert(
                        {
                            "group": group,
                            "name": name,
                            "tenant_id": tenant_id,
                            "locked": False,
                            "payload": _encode(payload),
                        }
                    )
                else:
                    await (
                        self._qb()
                        .where("group", group)
                        .where("name", name)
                        .where("tenant_id", tenant_id)
                        .update({"payload": _encode(payload)})
                    )

        _run(_update())

    def delete_property(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> None:
        async def _delete() -> None:
            await (
                self._qb()
                .where("group", group)
                .where("name", name)
                .where("tenant_id", tenant_id)
                .delete()
            )

        _run(_delete())

    def lock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        async def _lock() -> None:
            for name in properties:
                await (
                    self._qb()
                    .where("group", group)
                    .where("name", name)
                    .where("tenant_id", tenant_id)
                    .update({"locked": True})
                )

        _run(_lock())

    def unlock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        async def _unlock() -> None:
            for name in properties:
                await (
                    self._qb()
                    .where("group", group)
                    .where("name", name)
                    .where("tenant_id", tenant_id)
                    .update({"locked": False})
                )

        _run(_unlock())

    def get_locked_properties(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> list[str]:
        async def _locked() -> list[str]:
            rows = await (
                self._qb()
                .where("group", group)
                .where("tenant_id", tenant_id)
                .where("locked", True)
                .get()
            )
            return sorted(str(r["name"]) for r in rows)

        return list(_run(_locked()))
