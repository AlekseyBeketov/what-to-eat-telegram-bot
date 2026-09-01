from pathlib import Path

import pytest_asyncio

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.database import Database
from what_to_eat_bot.repositories.app import AppRepository


@pytest_asyncio.fixture
async def repository(tmp_path: Path) -> AppRepository:
    database = Database(tmp_path / "test.sqlite3")
    await database.migrate()
    return AppRepository(database)


@pytest_asyncio.fixture
async def service(repository: AppRepository) -> MealService:
    return MealService(repository)
