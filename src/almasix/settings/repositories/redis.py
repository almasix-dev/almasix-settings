"""Redis-backed settings repository (optional extra)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from almasix.settings.exceptions import MissingRedisExtra
from almasix.settings.tenant import GLOBAL_TENANT_ID


def _require_redis() -> None:
    try:
        import redis  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise MissingRedisExtra(
            "Redis settings repository requires the optional extra: "
            "pip install almasix-settings[redis]"
        ) from exc


def _encode(payload: Any) -> str:
    return json.dumps({"payload": payload, "locked": False})


def _encode_row(payload: Any, *, locked: bool) -> str:
    return json.dumps({"payload": payload, "locked": bool(locked)})


def _decode_row(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"payload": None, "locked": False}
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    data = json.loads(str(raw))
    if isinstance(data, dict) and "payload" in data:
        return {"payload": data.get("payload"), "locked": bool(data.get("locked"))}
    return {"payload": data, "locked": False}


class RedisSettingsRepository:
    """Store settings properties in Redis.

    Key shape: ``{prefix}:{tenant|global}:{group}:{name}``.
    Requires ``pip install almasix-settings[redis]`` and a bootstrapped Almasix Redis manager.
    """

    def __init__(
        self,
        *,
        prefix: str = "settings",
        connection: str | None = None,
    ) -> None:
        _require_redis()
        self.prefix = prefix.rstrip(":")
        self.connection = connection

    def _tenant_segment(self, tenant_id: str) -> str:
        return tenant_id if tenant_id else "global"

    def _key(self, group: str, name: str, tenant_id: str) -> str:
        return f"{self.prefix}:{self._tenant_segment(tenant_id)}:{group}:{name}"

    def _pattern(self, group: str, tenant_id: str) -> str:
        return f"{self.prefix}:{self._tenant_segment(tenant_id)}:{group}:*"

    def _client(self) -> Any:
        from almasix.redis import Redis

        return Redis

    def get_properties_in_group(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> dict[str, Any]:
        client = self._client()
        # Scan via known keys is not available without KEYS; use KEYS for v1 simplicity.
        pattern = self._pattern(group, tenant_id)
        redis = client.connection(self.connection)

        async def _scan() -> dict[str, Any]:
            out: dict[str, Any] = {}
            async for key in redis.scan_iter(match=pattern):
                key_s = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
                name = key_s.rsplit(":", 1)[-1]
                raw = await redis.get(key)
                out[name] = _decode_row(raw)["payload"]
            return out

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_scan())
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _scan()).result()

    def check_if_property_exists(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> bool:
        return self._client().get(self._key(group, name, tenant_id), connection=self.connection) is not None

    def get_property_payload(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> Any:
        raw = self._client().get(self._key(group, name, tenant_id), connection=self.connection)
        if raw is None:
            return None
        return _decode_row(raw)["payload"]

    def create_property(
        self,
        group: str,
        name: str,
        payload: Any,
        *,
        locked: bool = False,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        self._client().set(
            self._key(group, name, tenant_id),
            _encode_row(payload, locked=locked),
            connection=self.connection,
        )

    def update_properties_payload(
        self,
        group: str,
        properties: Mapping[str, Any],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name, payload in properties.items():
            key = self._key(group, name, tenant_id)
            raw = self._client().get(key, connection=self.connection)
            locked = _decode_row(raw)["locked"] if raw is not None else False
            self._client().set(key, _encode_row(payload, locked=locked), connection=self.connection)

    def delete_property(
        self, group: str, name: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> None:
        self._client().delete(self._key(group, name, tenant_id), connection=self.connection)

    def lock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name in properties:
            key = self._key(group, name, tenant_id)
            raw = self._client().get(key, connection=self.connection)
            if raw is None:
                continue
            row = _decode_row(raw)
            self._client().set(
                key, _encode_row(row["payload"], locked=True), connection=self.connection
            )

    def unlock_properties(
        self,
        group: str,
        properties: Sequence[str],
        *,
        tenant_id: str = GLOBAL_TENANT_ID,
    ) -> None:
        for name in properties:
            key = self._key(group, name, tenant_id)
            raw = self._client().get(key, connection=self.connection)
            if raw is None:
                continue
            row = _decode_row(raw)
            self._client().set(
                key, _encode_row(row["payload"], locked=False), connection=self.connection
            )

    def get_locked_properties(
        self, group: str, *, tenant_id: str = GLOBAL_TENANT_ID
    ) -> list[str]:
        props = self.get_properties_in_group(group, tenant_id=tenant_id)
        locked: list[str] = []
        for name in props:
            raw = self._client().get(self._key(group, name, tenant_id), connection=self.connection)
            if raw is not None and _decode_row(raw)["locked"]:
                locked.append(name)
        return sorted(locked)
