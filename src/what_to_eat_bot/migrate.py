import asyncio

from what_to_eat_bot.config import get_settings
from what_to_eat_bot.database import Database


async def migrate() -> None:
    settings = get_settings()
    await Database(settings.database_path).migrate()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
