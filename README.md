# Almasix Settings

Typed, database-backed application settings for Almasix — inspired by Spatie Laravel Settings, taught on Orbit/Almasix terms.

## Install

```bash
pip install almasix-settings
# optional Redis repository:
pip install almasix-settings[redis]
```

Register the provider (auto via `almasix.providers` entry point when discovered) and run migrations:

```bash
smith migrate
```

## Define settings

```python
from almasix.settings import Settings

class GeneralSettings(Settings):
    site_name: str
    site_active: bool
    api_token: str

    @classmethod
    def group(cls) -> str:
        return "general"

    @classmethod
    def encrypted(cls) -> tuple[str, ...]:
        return ("api_token",)
```

Seed defaults with a settings property migration:

```python
from almasix.settings.migrations import SettingsMigration

class CreateGeneralSettings(SettingsMigration):
    async def up(self) -> None:
        self.migrator.in_group("general", lambda b: (
            b.add("site_name", "Orbit"),
            b.add("site_active", True),
            b.add_encrypted("api_token", ""),
        ))
```

```bash
smith make:settings General
smith make:settings-migration create_general_settings
smith settings:migrate
```

## Load and save

```python
settings = GeneralSettings.load()
settings.site_name = "Acme"
settings.save()
```

Encrypted properties use Almasix `Crypt` (`APP_KEY` / `APP_PREVIOUS_KEYS`). Locked properties are skipped on save.

## Tenancy

Mark a class tenant-scoped so each tenant gets its own property set. Global defaults (`tenant_id=""`) are used until a tenant saves its own values.

```python
class MailSettings(Settings):
    tenant_scoped = True
    from_address: str

    @classmethod
    def group(cls) -> str:
        return "mail"
```

Orbit’s settings plugin binds the tenant resolver to the panel tenant automatically. Outside Orbit:

```python
from almasix.settings import set_current_tenant, set_tenant_resolver

set_current_tenant("acme")
# or
set_tenant_resolver(lambda: current_team_id())
```

## Repositories

Default: **database** (`settings` table with nullable-friendly `tenant_id`, empty string = global).

Also ships:

- `memory` — tests / demos
- `redis` — optional extra; keys `{prefix}:{tenant|global}:{group}:{name}`

```python
# config/settings.py
"default_repository": "database",  # or "redis" / "memory"
```

## Panel UI

Install [`almasix-orbit-settings`](https://github.com/almasix-dev/almasix-orbit-settings) and register `SettingsPlugin` on your Orbit panel to manage settings visually.

## License

MIT
