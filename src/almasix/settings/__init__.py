"""Typed application settings for Almasix."""

from almasix.settings.exceptions import (
    MissingRedisExtra,
    MissingSettings,
    SettingsError,
    SettingsPropertyLocked,
    UnknownRepository,
)
from almasix.settings.migrations import SettingsMigration, SettingsMigrator
from almasix.settings.repository import (
    SettingsRepository,
    bootstrap_default_repositories,
    get_repository,
    register_repository,
    set_default_repository,
)
from almasix.settings.settings import Settings
from almasix.settings.tenant import (
    GLOBAL_TENANT_ID,
    clear_current_tenant,
    current_tenant_id,
    normalize_tenant_id,
    set_current_tenant,
    set_tenant_resolver,
)

__all__ = [
    "GLOBAL_TENANT_ID",
    "MissingRedisExtra",
    "MissingSettings",
    "Settings",
    "SettingsError",
    "SettingsMigration",
    "SettingsMigrator",
    "SettingsPropertyLocked",
    "SettingsRepository",
    "UnknownRepository",
    "bootstrap_default_repositories",
    "clear_current_tenant",
    "current_tenant_id",
    "get_repository",
    "normalize_tenant_id",
    "register_repository",
    "set_current_tenant",
    "set_default_repository",
    "set_tenant_resolver",
]

# Ensure memory/database repos exist for library use outside a full app boot.
bootstrap_default_repositories()
set_default_repository("memory")
