"""Settings package exceptions."""

from __future__ import annotations


class SettingsError(Exception):
    """Base error for almasix.settings."""


class MissingSettings(SettingsError):
    """Raised when a settings property has no stored value and no default."""


class SettingsPropertyLocked(SettingsError):
    """Raised when writing a locked settings property."""


class MissingRedisExtra(SettingsError):
    """Raised when the Redis repository is used without ``almasix-settings[redis]``."""


class UnknownRepository(SettingsError):
    """Raised when a repository name is not configured."""
