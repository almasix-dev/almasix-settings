"""Settings package service provider."""

from __future__ import annotations

from pathlib import Path

from almasix.providers import ServiceProvider

_HERE = Path(__file__).resolve().parent


class SettingsServiceProvider(ServiceProvider):
    """Registers settings config, migrations, repositories, and smith commands."""

    def register(self) -> None:
        self.merge_config_from(_HERE / "config" / "settings.py", "settings")
        from almasix.settings.repository import (
            bootstrap_default_repositories,
            set_default_repository,
        )

        bootstrap_default_repositories()
        default = str(self.app.config.get("settings.default_repository") or "database")
        set_default_repository(default)

    def boot(self) -> None:
        self.publishes(
            {_HERE / "config" / "settings.py": self.app.path("config", "settings.py")},
            "settings-config",
        )
        migrations = _HERE / "database" / "migrations"
        self.load_migrations_from(migrations)
        self.publishes_migrations(
            {
                migrations / "create_settings_tables.py": (
                    "database/migrations/create_settings_tables.py"
                ),
            },
            "settings-migrations",
        )
        from almasix.settings.console import (
            MakeSettingsCommand,
            MakeSettingsMigrationCommand,
            SettingsClearCacheCommand,
            SettingsMigrateCommand,
        )

        self.commands(
            [
                MakeSettingsCommand,
                MakeSettingsMigrationCommand,
                SettingsMigrateCommand,
                SettingsClearCacheCommand,
            ]
        )
