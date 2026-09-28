"""Create the settings storage tables."""

from __future__ import annotations

from almasix.orm import Blueprint, Migration, Schema


class CreateSettingsTables(Migration):
    async def up(self) -> None:
        await Schema.create("settings", self._settings)
        await Schema.create("settings_migrations", self._settings_migrations)

    async def down(self) -> None:
        await Schema.drop_if_exists("settings_migrations")
        await Schema.drop_if_exists("settings")

    def _settings(self, table: Blueprint) -> None:
        table.id()
        table.string("group")
        table.string("name")
        # Empty string = global tenant (unique-friendly across SQLite/Postgres/MySQL).
        table.string("tenant_id").default("")
        table.boolean("locked").default(False)
        table.json("payload").nullable()
        table.timestamps()
        table.unique(["group", "name", "tenant_id"])
        table.index(["group", "tenant_id"])

    def _settings_migrations(self, table: Blueprint) -> None:
        table.id()
        table.string("migration")
        table.integer("batch")
        table.timestamps()
        table.unique(["migration"])
