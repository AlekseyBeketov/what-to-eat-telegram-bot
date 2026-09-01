from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from what_to_eat_bot.application.normalization import normalize_text
from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.handlers.formatters import dish_text
from what_to_eat_bot.handlers.keyboards import buttons, dish_card, dish_list
from what_to_eat_bot.handlers.presentation import (
    ALL_DISHES_LABEL,
    MEAL_CHOICE_LABELS,
    PAGE_SIZE,
)
from what_to_eat_bot.handlers.states import SearchDish
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="catalog")


async def show_root(message: Message, user_id: int, repository: AppRepository) -> None:
    breakfasts = await repository.count_dishes(user_id, MealType.BREAKFAST)
    mains = await repository.count_dishes(user_id, MealType.MAIN)
    await message.answer(
        "<b>Мои блюда</b>",
        reply_markup=buttons(
            [
                [
                    (f"☕️ Завтраки — {breakfasts}", "catalog:type:breakfast"),
                    (f"🍗 Обеды/ужины — {mains}", "catalog:type:main"),
                ],
                [(ALL_DISHES_LABEL, "catalog:type:any"), ("⭐ Избранное", "catalog:favorites")],
                [("🔎 Поиск", "catalog:search"), ("🕘 Недавно готовил", "catalog:history")],
            ]
        ),
    )


@router.message(F.text == "📚 Мои блюда")
async def catalog_menu(message: Message, repository: AppRepository) -> None:
    if message.from_user:
        await show_root(message, message.from_user.id, repository)


@router.message(F.text == "⭐ Избранное")
async def favorites_message(message: Message, state: FSMContext, repository: AppRepository) -> None:
    if not message.from_user:
        return
    await state.update_data(catalog_type="any", catalog_favorites=True, catalog_query=None)
    dishes = await repository.list_dishes(
        message.from_user.id, favorites_only=True, limit=PAGE_SIZE + 1
    )
    await message.answer(
        "<b>Избранные блюда</b>" if dishes else "В избранном пока пусто.",
        reply_markup=dish_list(dishes, 0),
    )


@router.callback_query(F.data == "catalog:root")
async def catalog_root(callback: CallbackQuery, repository: AppRepository) -> None:
    await callback.answer()
    if callback.message and callback.from_user:
        await show_root(callback.message, callback.from_user.id, repository)


@router.callback_query(F.data.startswith("catalog:type:"))
async def catalog_type(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(catalog_type=value, catalog_favorites=False, catalog_query=None)
    meal_type = None if value == "any" else MealType(value)
    dishes = await repository.list_dishes(
        callback.from_user.id, meal_type=meal_type, limit=PAGE_SIZE + 1
    )
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(MEAL_CHOICE_LABELS[value])
        await callback.message.answer(
            "Выберите блюдо:" if dishes else "В этой категории пока нет блюд.",
            reply_markup=dish_list(dishes, 0),
        )


@router.callback_query(F.data == "catalog:favorites")
async def catalog_favorites(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    await state.update_data(catalog_type="any", catalog_favorites=True, catalog_query=None)
    dishes = await repository.list_dishes(
        callback.from_user.id, favorites_only=True, limit=PAGE_SIZE + 1
    )
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text("⭐ Избранное")
        await callback.message.answer(
            "Избранное:" if dishes else "В избранном пока пусто.",
            reply_markup=dish_list(dishes, 0),
        )


@router.callback_query(F.data.startswith("catalog:page:"))
async def catalog_page(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    page = max(0, int(callback.data.rsplit(":", 1)[-1]))
    data = await state.get_data()
    value = data.get("catalog_type", "any")
    meal_type = None if value == "any" else MealType(value)
    dishes = await repository.list_dishes(
        callback.from_user.id,
        meal_type=meal_type,
        favorites_only=bool(data.get("catalog_favorites")),
        query=data.get("catalog_query"),
        limit=PAGE_SIZE + 1,
        offset=page * PAGE_SIZE,
    )
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=dish_list(dishes, page))


@router.callback_query(F.data == "catalog:search")
async def search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchDish.query)
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text("🔎 Поиск")
        await callback.message.answer(
            "Введите часть названия блюда:",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )


@router.message(SearchDish.query, F.text)
async def search_query(message: Message, state: FSMContext, service: MealService) -> None:
    if not message.from_user:
        return
    query = normalize_text(message.text or "")
    dishes = await service.search_dishes(message.from_user.id, query, limit=PAGE_SIZE + 1)
    await state.set_state(None)
    await state.update_data(catalog_type="any", catalog_favorites=False, catalog_query=query)
    await message.answer(
        "Результаты поиска:" if dishes else "Ничего не найдено.",
        reply_markup=dish_list(dishes, 0),
    )


@router.callback_query(F.data.startswith("dish:view:"))
async def view_dish(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        dish = await repository.get_dish(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            dish_text(dish), reply_markup=dish_card(dish, callback.from_user.id)
        )


@router.callback_query(F.data.startswith("dish:fav:"))
async def toggle_favorite(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        favorite = await repository.toggle_favorite_dish(callback.from_user.id, dish_id)
        dish = await repository.get_dish(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer("Добавлено в избранное" if favorite else "Убрано из избранного")
    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=dish_card(dish, callback.from_user.id)
        )


@router.callback_query(F.data.startswith("dish:cooked:"))
async def mark_cooked(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        await repository.mark_cooked(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer("Отмечено: приготовил ✅", show_alert=True)


@router.callback_query(F.data.startswith("dish:delete:"))
async def delete_prompt(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        dish = await repository.get_dish(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    if dish.author_id != callback.from_user.id:
        await callback.answer("Удалить блюдо может только автор", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Удалить «{escape(dish.name)}»?",
            reply_markup=buttons(
                [
                    [
                        ("🗑 Да, удалить", f"dish:confirm_delete:{dish.id}"),
                        ("❌ Отмена", "catalog:root"),
                    ]
                ]
            ),
        )


@router.callback_query(F.data.startswith("dish:confirm_delete:"))
async def delete_confirm(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    deleted = await repository.delete_dish(callback.from_user.id, dish_id)
    await callback.answer("Удалено" if deleted else "Действие устарело", show_alert=not deleted)
    if callback.message and deleted:
        await callback.message.edit_text("Блюдо удалено.")


@router.callback_query(F.data == "catalog:history")
async def history(callback: CallbackQuery, repository: AppRepository) -> None:
    entries = await repository.recent_cooked(callback.from_user.id, limit=PAGE_SIZE)
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text("🕘 Недавно готовил")
        text = (
            "<b>Недавно готовил:</b>\n"
            + "\n".join(f"• {escape(dish.name)} — {cooked:%d.%m.%Y}" for dish, cooked in entries)
            if entries
            else "История пока пуста."
        )
        await callback.message.answer(text)
