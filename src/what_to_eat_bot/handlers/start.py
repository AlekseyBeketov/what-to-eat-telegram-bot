from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.handlers.keyboards import MAIN_MENU, buttons, onboarding
from what_to_eat_bot.handlers.states import FamilyFlow
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="start")


async def register_user(message: Message, repository: AppRepository) -> int:
    if message.from_user is None:
        raise RuntimeError("Update has no user")
    await repository.ensure_user(
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username,
    )
    return message.from_user.id


@router.message(CommandStart())
async def start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    repository: AppRepository,
    service: MealService,
) -> None:
    user_id = await register_user(message, repository)
    await state.clear()
    if command.args and command.args.startswith("family_"):
        token = command.args.removeprefix("family_")
        try:
            invite = await service.inspect_family_invite(token)
        except DomainError as error:
            await message.answer(str(error), reply_markup=MAIN_MENU)
            return
        await state.set_state(FamilyFlow.confirm_join)
        await state.update_data(invite_token=token)
        await message.answer(
            f"Вы присоединяетесь к семье «{escape(invite.family_name)}» пользователя "
            f"{escape(invite.inviter_name)}. После подтверждения каталоги блюд будут общими.",
            reply_markup=buttons([[("✅ Вступить", "family:join"), ("❌ Отмена", "flow:cancel")]]),
        )
        return
    count = await repository.count_dishes(user_id)
    if count == 0:
        await message.answer(
            "<b>Я помогу решить, что приготовить.</b>\n\n"
            "Для начала добавь несколько блюд, которые ты обычно готовишь.",
            reply_markup=onboarding(),
        )
    else:
        await message.answer("Что будем готовить?", reply_markup=MAIN_MENU)


@router.message(Command("help"))
@router.callback_query(F.data == "help:how")
async def help_message(event: Message | CallbackQuery) -> None:
    text = (
        "Добавь привычные блюда и их ингредиенты. Затем выбери или введи продукты — "
        "бот покажет подходящие блюда и чего не хватает."
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text, reply_markup=MAIN_MENU)
    else:
        await event.answer(text, reply_markup=MAIN_MENU)


@router.callback_query(F.data == "flow:cancel")
async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.answer("Действие отменено.", reply_markup=MAIN_MENU)


@router.message(
    F.text.func(lambda value: isinstance(value, str) and value.strip().casefold() == "отмена")
)
async def cancel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=MAIN_MENU)
