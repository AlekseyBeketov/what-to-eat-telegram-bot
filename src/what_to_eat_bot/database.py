from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA busy_timeout = 5000")
        await db.execute("PRAGMA journal_mode = WAL")
        try:
            yield db
        finally:
            await db.close()

    async def migrate(self) -> None:
        async with self.connect() as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            await db.commit()
            cursor = await db.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in await cursor.fetchall()}
            migration_dir = files("what_to_eat_bot").joinpath("migrations")
            for item in sorted(migration_dir.iterdir(), key=lambda entry: entry.name):
                if item.name.endswith(".sql") and item.name not in applied:
                    version = item.name.replace("'", "''")
                    script = item.read_text(encoding="utf-8")
                    transactional_script = (
                        "BEGIN IMMEDIATE;\n"
                        f"{script}\n"
                        "INSERT INTO schema_migrations(version) "
                        f"VALUES ('{version}');\n"
                        "COMMIT;"
                    )
                    try:
                        await db.executescript(transactional_script)
                    except Exception:
                        await db.rollback()
                        raise
