import asyncio
import logging

from pydantic import ValidationError

from what_to_eat_bot.app import run_polling
from what_to_eat_bot.config import get_settings
from what_to_eat_bot.logging import configure_logging


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as error:
        missing = [
            str(item["loc"][0]).upper() for item in error.errors() if item["type"] == "missing"
        ]
        names = ", ".join(missing) or "configuration"
        raise SystemExit(f"Missing or invalid environment variable: {names}") from None
    configure_logging(settings.log_level)
    try:
        asyncio.run(run_polling(settings))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Interrupted")


if __name__ == "__main__":
    main()
