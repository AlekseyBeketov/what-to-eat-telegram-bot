import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import ErrorEvent

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.config import Settings
from what_to_eat_bot.database import Database
from what_to_eat_bot.handlers import (
    add_dish,
    catalog,
    edit_dish,
    family_proposals,
    recommend,
    settings_family,
    start,
)
from what_to_eat_bot.repositories.app import AppRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Application:
    bot: Bot
    dispatcher: Dispatcher
    database: Database
    repository: AppRepository
    service: MealService


async def create_application(settings: Settings) -> Application:
    database = Database(settings.database_path)
    await database.migrate()
    repository = AppRepository(database)
    service = MealService(repository, invite_ttl_hours=settings.invite_ttl_hours)
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(
        storage=MemoryStorage(),
        events_isolation=SimpleEventIsolation(),
        repository=repository,
        service=service,
        settings=settings,
    )
    dispatcher.include_routers(
        start.router,
        add_dish.router,
        edit_dish.router,
        catalog.router,
        family_proposals.router,
        recommend.router,
        settings_family.router,
        _fallback_router(),
    )

    @dispatcher.error()
    async def global_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled update error", exc_info=event.exception)
        update = event.update
        message = update.message or (
            update.callback_query.message if update.callback_query else None
        )
        if message:
            await message.answer(
                "Не удалось выполнить действие. Попробуйте ещё раз или вернитесь в главное меню."
            )
        if update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        return True

    return Application(bot, dispatcher, database, repository, service)


def _fallback_router() -> Router:
    from aiogram.types import CallbackQuery, Message

    router = Router(name="fallback")

    @router.callback_query()
    async def stale_callback(callback: CallbackQuery) -> None:
        await callback.answer("Действие устарело. Откройте нужный раздел заново.", show_alert=True)

    @router.message()
    async def unknown(message: Message) -> None:
        await message.answer("Не понял действие. Используйте кнопки меню или /start.")

    return router


async def run_polling(settings: Settings) -> None:
    application = await create_application(settings)
    expiration_task = asyncio.create_task(
        family_proposals.expiration_worker(application.bot, application.service)
    )
    logger.info("Starting long polling")
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
        await application.dispatcher.start_polling(
            application.bot,
            allowed_updates=application.dispatcher.resolve_used_update_types(),
            handle_signals=True,
            close_bot_session=False,
        )
    finally:
        expiration_task.cancel()
        with suppress(asyncio.CancelledError):
            await expiration_task
        await application.dispatcher.storage.close()
        await application.bot.session.close()
        logger.info("Long polling stopped")
