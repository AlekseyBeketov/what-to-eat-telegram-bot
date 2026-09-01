from pathlib import Path

from what_to_eat_bot.application.normalization import normalize_text
from what_to_eat_bot.database import Database
from what_to_eat_bot.repositories.app import AppRepository

ALEKSEY_TELEGRAM_ID = 964423991


async def test_migrate_clean_database_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "fresh.sqlite3")
    await database.migrate()
    await database.migrate()
    async with database.connect() as db:
        version = await (await db.execute("SELECT COUNT(*) FROM schema_migrations")).fetchone()
        foreign_keys = await (await db.execute("PRAGMA foreign_keys")).fetchone()
        tables = await (
            await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    names = {row[0] for row in tables}
    assert version[0] == 2
    assert foreign_keys[0] == 1
    assert {"users", "dishes", "ingredients", "family_invites", "dish_tags"} <= names


async def test_seed_catalog_is_loaded_once_and_search_is_case_and_yo_insensitive(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "seed.sqlite3")
    await database.migrate()
    await database.migrate()

    async with database.connect() as db:
        dish_count = await (
            await db.execute(
                "SELECT COUNT(*) FROM dishes WHERE author_id = ?", (ALEKSEY_TELEGRAM_ID,)
            )
        ).fetchone()
        links_count = await (
            await db.execute(
                """
                SELECT COUNT(*)
                FROM dish_ingredients di
                JOIN dishes d ON d.id = di.dish_id
                WHERE d.author_id = ?
                """,
                (ALEKSEY_TELEGRAM_ID,),
            )
        ).fetchone()
        versions = await (await db.execute("SELECT COUNT(*) FROM schema_migrations")).fetchone()

    assert dish_count[0] == 22
    assert links_count[0] == 79
    assert versions[0] == 2

    repository = AppRepository(database)
    upper_case = await repository.list_dishes(
        ALEKSEY_TELEGRAM_ID,
        query=normalize_text("НАГЕТСЫ"),
    )
    with_yo = await repository.list_dishes(
        ALEKSEY_TELEGRAM_ID,
        query=normalize_text("ТУШЁНКОЙ"),
    )
    assert [dish.name for dish in upper_case] == ["Нагетсы"]
    assert {dish.name for dish in with_yo} == {
        "Греча с тушенкой",
        "Картошка с тушенкой",
        "Макароны с тушенкой",
    }
    stew = await repository.resolve_ingredient(normalize_text("ТУШЁНКА"))
    assert stew is not None
    assert stew.normalized_name == "тушенка"


async def test_seed_catalog_uses_confirmed_ingredients(tmp_path: Path) -> None:
    database = Database(tmp_path / "ingredients.sqlite3")
    await database.migrate()
    repository = AppRepository(database)

    groats = await repository.list_dishes(
        ALEKSEY_TELEGRAM_ID,
        query=normalize_text("греча с тушёнкой"),
    )
    chicken_steak = await repository.list_dishes(
        ALEKSEY_TELEGRAM_ID,
        query=normalize_text("стейки из курицы"),
    )

    assert {item.normalized_name for item in groats[0].ingredients} == {
        "гречка",
        "сыр",
        "тушенка",
    }
    assert {item.normalized_name for item in chicken_steak[0].ingredients} == {"курица"}
