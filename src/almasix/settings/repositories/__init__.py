"""Settings repository implementations."""

from almasix.settings.repositories.database import DatabaseSettingsRepository
from almasix.settings.repositories.memory import MemorySettingsRepository

__all__ = [
    "DatabaseSettingsRepository",
    "MemorySettingsRepository",
]

try:
    from almasix.settings.repositories.redis import (
        RedisSettingsRepository as RedisSettingsRepository,
    )

    __all__.append("RedisSettingsRepository")
except Exception:  # pragma: no cover
    pass
