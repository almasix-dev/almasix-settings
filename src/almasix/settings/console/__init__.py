"""Smith commands for settings."""

from __future__ import annotations

import re
from pathlib import Path

from almasix.console.command import Command


def _snake(name: str) -> str:
    text = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text).lower()


def _studly(name: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[_\-\s]+", name) if part)


class MakeSettingsCommand(Command):
    signature = "make:settings {name : Settings class name (e.g. GeneralSettings)}"
    description = "Create a typed Settings class under app/settings"

    def handle(self) -> int:
        raw = str(self.argument("name") or "").strip()
        if not raw:
            self.error("name is required")
            return self.FAILURE
        class_name = _studly(raw)
        if not class_name.endswith("Settings"):
            class_name = f"{class_name}Settings"
        group = _snake(class_name.removesuffix("Settings"))
        path = Path(self.app.base_path) / "app" / "settings" / f"{_snake(class_name)}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.warn(f"Already exists: {path}")
            return self.SUCCESS
        path.write_text(
            (
                '"""Application settings."""\n\n'
                "from __future__ import annotations\n\n"
                "from almasix.settings import Settings\n\n\n"
                f"class {class_name}(Settings):\n"
                f'    """Settings group ``{group}``."""\n\n'
                "    site_name: str\n\n"
                "    @classmethod\n"
                "    def group(cls) -> str:\n"
                f'        return "{group}"\n'
            ),
            encoding="utf-8",
        )
        self.success(f"Created {path}")
        return self.SUCCESS


class MakeSettingsMigrationCommand(Command):
    signature = (
        "make:settings-migration {name : Migration name (e.g. create_general_settings)}"
    )
    description = "Create a settings property migration under database/settings"

    def handle(self) -> int:
        from datetime import UTC, datetime

        raw = str(self.argument("name") or "").strip()
        if not raw:
            self.error("name is required")
            return self.FAILURE
        stamp = datetime.now(UTC).strftime("%Y_%m_%d_%H%M%S")
        slug = _snake(raw)
        class_name = _studly(raw)
        path = Path(self.app.base_path) / "database" / "settings" / f"{stamp}_{slug}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            (
                '"""Settings property migration."""\n\n'
                "from __future__ import annotations\n\n"
                "from almasix.settings.migrations import SettingsMigration\n\n\n"
                f"class {class_name}(SettingsMigration):\n"
                "    async def up(self) -> None:\n"
                '        self.migrator.in_group("general", lambda b: (\n'
                '            b.add("site_name", "Orbit"),\n'
                "        ))\n"
            ),
            encoding="utf-8",
        )
        self.success(f"Created {path}")
        return self.SUCCESS


class SettingsMigrateCommand(Command):
    signature = "settings:migrate"
    description = "Run pending settings property migrations"

    def handle(self) -> int:
        from almasix.settings.migrator_runner import run_settings_migrations

        count = run_settings_migrations(base_path=str(self.app.base_path))
        self.success(f"Ran {count} settings migration(s)")
        return self.SUCCESS


class SettingsClearCacheCommand(Command):
    signature = "settings:clear-cache"
    description = "Clear the settings cache (no-op when cache is disabled)"

    def handle(self) -> int:
        self.info("Settings cache cleared.")
        return self.SUCCESS
