"""Run property migrations from ``database/settings``."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from almasix.settings.migrations import SettingsMigration
from almasix.settings.repository import get_repository

_APPLIED: set[str] = set()


def reset_applied_migrations() -> None:
    _APPLIED.clear()


def _load_migration(path: Path) -> type[SettingsMigration] | None:
    spec = importlib.util.spec_from_file_location(f"settings_mig_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for value in vars(module).values():
        if (
            isinstance(value, type)
            and issubclass(value, SettingsMigration)
            and value is not SettingsMigration
        ):
            return value
    return None


def run_settings_migrations(
    *,
    base_path: str | Path,
    paths: list[str] | None = None,
    repository_name: str | None = None,
) -> int:
    """Execute pending ``SettingsMigration`` subclasses. Returns count ran."""
    root = Path(base_path)
    search = paths or ["database/settings"]
    files: list[Path] = []
    for rel in search:
        folder = root / rel
        if not folder.is_dir():
            continue
        files.extend(sorted(folder.glob("*.py")))
    files = [f for f in files if not f.name.startswith("_")]
    count = 0
    for path in files:
        key = path.name
        if key in _APPLIED:
            continue
        cls = _load_migration(path)
        if cls is None:
            continue
        migration = cls()
        if repository_name:
            migration.migrator.repository_name = repository_name
        migration_key = key

        async def _up(mig: SettingsMigration = migration) -> None:
            await mig.up()

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_up())
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _up()).result()
        _APPLIED.add(migration_key)
        # Best-effort persist applied marker when using database repo.
        try:
            repo = get_repository(repository_name)
            if hasattr(repo, "table"):  # DatabaseSettingsRepository
                from almasix.orm.facade import DB

                async def _mark(name: str = migration_key) -> None:
                    await DB.table("settings_migrations").insert(
                        {"migration": name, "batch": 1}
                    )

                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(_mark())
                else:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(asyncio.run, _mark()).result()
        except Exception:
            pass
        count += 1
    return count
