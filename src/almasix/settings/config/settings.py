"""Default settings package config."""

config = {
    "default_repository": "database",
    "repositories": {
        "database": {
            "type": "almasix.settings.repositories.database.DatabaseSettingsRepository",
            "table": "settings",
            "connection": None,
        },
        "redis": {
            "type": "almasix.settings.repositories.redis.RedisSettingsRepository",
            "connection": None,
            "prefix": "settings",
        },
        "memory": {
            "type": "almasix.settings.repositories.memory.MemorySettingsRepository",
        },
    },
    "auto_discover_settings": ["app/settings"],
    "migrations_paths": ["database/settings"],
    "cache": {
        "enabled": False,
        "prefix": "settings",
    },
}
