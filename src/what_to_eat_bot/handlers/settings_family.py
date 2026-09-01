from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.config import Settings
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.handlers.keyboards import buttons
from what_to_eat_bot.handlers.presentation import (
    LIST_INPUT_HINT,
    NEXT_PAGE_LABEL,
    PAGE_SIZE,
    PREVIOUS_PAGE_LABEL,
)
from what_to_eat_bot.handlers.states import FamilyFlow, SettingsInput
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="settings_family")


def _category_list_view(categories: list[tuple[str, str]], page: int):
    start = page * PAGE_SIZE
    visible = categories[start : start + PAGE_SIZE]
    text = "<b>Категории ингредиентов:</b>\n" + "\n".join(
        f"• {escape(name)}" for _, name in visible
    )
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append((PREVIOUS_PAGE_LABEL, f"settings:categories:{page - 1}"))
    if start + PAGE_SIZE < len(categories):
        nav.append((NEXT_PAGE_LABEL, f"settings:categories:{page + 1}"))
    rows = [nav] if nav else []
    rows.append([("❌ Отмена", "flow:cancel")])
    return text, buttons(rows)


@router.message(F.text == "⚙️ Настройки")
async def settings_menu_message(message: Message) -> None:
    await show_settings(message)


async def show_settings(message: Message) -> None:
    await message.answer(
        "<b>Настройки</b>",
        reply_markup=buttons(
            [
                [
                    ("🥫 Базовые продукты", "settings:basic"),
                    ("⭐ Любимые продукты", "settings:favorite"),
                ],
                [("🥕 Управление ингредиентами", "settings:ingredients")],
                [
                    ("📂 Категории", "settings:categories"),
                    ("🧹 Очистить частые", "settings:clear_usage"),
                ],
                [("👨‍👩‍👧 Моя семья", "family:menu")],
            ]
        ),
    )


@router.callback_query(F.data.in_({"settings:basic", "settings:favorite", "settings:ingredients"}))
async def settings_input_start(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.rsplit(":", 1)[-1]
    await state.set_state(SettingsInput.basic if mode == "basic" else SettingsInput.favorite)
    await state.update_data(settings_mode=mode)
    await callback.answer()
    if callback.message:
        prompts = {
            "basic": f"Введите продукты {LIST_INPUT_HINT}, которые считать всегда имеющимися:\n"
            "Для отмены нажмите кнопку или напишите «отмена».",
            "favorite": f"Введите любимые продукты {LIST_INPUT_HINT} для быстрого выбора:\n"
            "Для отмены нажмите кнопку или напишите «отмена».",
            "ingredients": "Введите название ингредиента. Если его нет, бот предложит создать:\n"
            "Для отмены нажмите кнопку или напишите «отмена».",
        }
        await callback.message.answer(
            prompts[mode], reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
        )


@router.message(SettingsInput.basic, F.text)
@router.message(SettingsInput.favorite, F.text)
async def settings_input_parse(
    message: Message, state: FSMContext, service: MealService, repository: AppRepository
) -> None:
    if not message.from_user:
        return
    data = await state.get_data()
    mode = data.get("settings_mode")
    resolved, missing = await service.parse_ingredients(message.text or "")
    await state.update_data(settings_ids=[item.id for item in resolved], settings_missing=missing)
    if missing:
        await message.answer(
            "Не найдены: " + ", ".join(escape(name) for name in missing[:PAGE_SIZE]),
            reply_markup=buttons(
                [[("✅ Создать", "settings:create_missing"), ("❌ Пропустить", "settings:apply")]]
                + [[("❌ Отмена", "flow:cancel")]]
            ),
        )
    else:
        await _apply_settings(message, state, repository, mode)


@router.callback_query(F.data == "settings:create_missing")
async def settings_create_missing(
    callback: CallbackQuery,
    state: FSMContext,
    service: MealService,
    repository: AppRepository,
) -> None:
    data = await state.get_data()
    ids = set(data.get("settings_ids", []))
    for name in data.get("settings_missing", []):
        ids.add((await service.create_ingredient(callback.from_user.id, name)).id)
    await state.update_data(settings_ids=sorted(ids), settings_missing=[])
    await callback.answer("Создано")
    if callback.message:
        await _apply_settings(
            callback.message, state, repository, data.get("settings_mode"), callback.from_user.id
        )


@router.callback_query(F.data == "settings:apply")
async def settings_apply(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    data = await state.get_data()
    await callback.answer()
    if callback.message:
        await _apply_settings(
            callback.message, state, repository, data.get("settings_mode"), callback.from_user.id
        )


async def _apply_settings(
    message: Message,
    state: FSMContext,
    repository: AppRepository,
    mode: str,
    user_id: int | None = None,
) -> None:
    actor = user_id or (message.from_user.id if message.from_user else 0)
    data = await state.get_data()
    ids = data.get("settings_ids", [])
    if mode == "basic":
        current = await repository.get_basic_ingredient_ids(actor)
        for ingredient_id in ids:
            await repository.set_basic_ingredient(
                actor, ingredient_id, ingredient_id not in current
            )
        text = "Базовые продукты переключены. Они не ухудшают подбор."
    elif mode == "favorite":
        current = await repository.get_favorite_ingredient_ids(actor)
        for ingredient_id in ids:
            await repository.set_favorite_ingredient(
                actor, ingredient_id, ingredient_id not in current
            )
        text = "Любимые продукты переключены."
    else:
        text = "Ингредиенты доступны в общем каталоге."
    await state.clear()
    await message.answer(text)


@router.callback_query(F.data == "settings:categories")
async def settings_categories(callback: CallbackQuery, repository: AppRepository) -> None:
    categories = await repository.list_categories()
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text("📂 Категории")
        text, markup = _category_list_view(categories, 0)
        await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("settings:categories:"))
async def settings_categories_page(callback: CallbackQuery, repository: AppRepository) -> None:
    page = max(0, int((callback.data or "").rsplit(":", 1)[-1]))
    categories = await repository.list_categories()
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        text, markup = _category_list_view(categories, page)
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "settings:clear_usage")
async def clear_usage_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Очистить статистику частых и недавних продуктов?",
            reply_markup=buttons(
                [[("🧹 Да, очистить", "settings:confirm_clear"), ("❌ Отмена", "flow:cancel")]]
            ),
        )


@router.callback_query(F.data == "settings:confirm_clear")
async def clear_usage(callback: CallbackQuery, repository: AppRepository) -> None:
    await repository.clear_ingredient_usage(callback.from_user.id)
    await callback.answer("Очищено")
    if callback.message:
        await callback.message.edit_text("Статистика продуктов очищена.")


@router.callback_query(F.data == "family:menu")
async def family_menu(callback: CallbackQuery, repository: AppRepository) -> None:
    info = await repository.family_info(callback.from_user.id)
    await callback.answer()
    if not callback.message:
        return
    if info:
        _, name, members = info
        member_text = "\n".join(
            f"• {escape(member_name)}" for _, member_name in members[:PAGE_SIZE]
        )
        await callback.message.answer(
            f"<b>Семья «{escape(name)}»</b>\n\n<b>Участники:</b>\n{member_text}",
            reply_markup=buttons(
                [
                    [("🔗 Пригласить", "family:invite"), ("👥 Участники", "family:members")],
                    [("🚪 Выйти из семьи", "family:leave")],
                ]
            ),
        )
    else:
        await callback.message.answer(
            "Вы пока не состоите в семье.",
            reply_markup=buttons([[("➕ Создать семью", "family:create")]]),
        )


@router.callback_query(F.data == "family:create")
async def family_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FamilyFlow.name)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Введите название семьи:", reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
        )


@router.message(FamilyFlow.name, F.text)
async def family_create_name(
    message: Message, state: FSMContext, repository: AppRepository
) -> None:
    if not message.from_user:
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(
            "Название слишком короткое.",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )
        return
    try:
        await repository.create_family(message.from_user.id, name)
    except DomainError as error:
        await message.answer(str(error), reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]))
        return
    await state.clear()
    await message.answer("Семья создана. Теперь можно отправить приглашение.")


@router.callback_query(F.data == "family:invite")
async def family_invite(callback: CallbackQuery, service: MealService, settings: Settings) -> None:
    try:
        token = await service.create_family_invite(callback.from_user.id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer("Приглашение создано")
    if callback.message:
        if settings.bot_username:
            invite = f"https://t.me/{settings.bot_username}?start=family_{token}"
            text = (
                "Отправьте эту одноразовую ссылку. Она действует "
                f"{settings.invite_ttl_hours} ч.:\n{invite}"
            )
        else:
            text = (
                "Код приглашения (действует "
                f"{settings.invite_ttl_hours} ч.):\n<code>{token}</code>\n"
                "Для deep-link задайте BOT_USERNAME."
            )
        await callback.message.answer(text)


@router.callback_query(FamilyFlow.confirm_join, F.data == "family:join")
async def family_join(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    token = (await state.get_data()).get("invite_token", "")
    try:
        await service.accept_family_invite(callback.from_user.id, token)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    await callback.answer("Вы вступили в семью")
    if callback.message:
        await callback.message.edit_text("Готово. Теперь каталоги блюд общие.")


@router.callback_query(F.data == "family:members")
async def family_members(callback: CallbackQuery, repository: AppRepository) -> None:
    info = await repository.family_info(callback.from_user.id)
    await callback.answer()
    if callback.message and info:
        await callback.message.answer(
            "<b>Участники:</b>\n"
            + "\n".join(f"• {escape(name)}" for _, name in info[2][:PAGE_SIZE])
        )


@router.callback_query(F.data == "family:leave")
async def family_leave_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "После выхода вы сохраните свои блюда, но перестанете видеть блюда остальных. Выйти?",
            reply_markup=buttons(
                [[("🚪 Да, выйти", "family:confirm_leave"), ("❌ Отмена", "flow:cancel")]]
            ),
        )


@router.callback_query(F.data == "family:confirm_leave")
async def family_leave(callback: CallbackQuery, repository: AppRepository) -> None:
    left = await repository.leave_family(callback.from_user.id)
    await callback.answer("Вы вышли из семьи" if left else "Вы уже не состоите в семье")
    if callback.message:
        await callback.message.edit_text(
            "Вы вышли из семьи. Ваши блюда сохранены." if left else "Семья не найдена."
        )
