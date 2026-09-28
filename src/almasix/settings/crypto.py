"""Encrypt / decrypt settings payloads via Almasix Crypt."""

from __future__ import annotations

from typing import Any


def encrypt_payload(value: Any) -> str:
    """Encrypt a JSON-safe value for storage."""
    from almasix.encryption import Crypt

    return Crypt.encrypt(value)


def decrypt_payload(payload: Any) -> Any:
    """Decrypt a value previously produced by :func:`encrypt_payload`."""
    if payload is None:
        return None
    from almasix.encryption import Crypt

    return Crypt.decrypt(str(payload))


def try_decrypt_payload(payload: Any) -> Any:
    """Decrypt when possible; return the raw payload if decryption fails."""
    if payload is None:
        return None
    try:
        return decrypt_payload(payload)
    except Exception:
        return payload
