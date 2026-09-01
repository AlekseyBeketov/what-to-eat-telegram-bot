from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.models import Dish, MealType, Recommendation
from what_to_eat_bot.handlers.formatters import recommendation_text, selected_text
from what_to_eat_bot.handlers.keyboards import (
    buttons,
    category_picker,
    empty_ingredient_picker,
    ingredient_picker,
    meal_types,
)
from what_to_eat_bot.handlers.presentation import (
    LIST_INPUT_HINT,
    MEAL_CHOICE_LABELS,
    NEXT_PAGE_LABEL,
    PAGE_SIZE,
    PREVIOUS_PAGE_LABEL,
)
from what_to_eat_bot.handlers.states import Recommend
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="recommend")

_QUICK_LABELS = {
    "frequent": "🔥 Частые",
    "recent": "🕘 Недавние",
    "favorite": "⭐ Избранные продукты",
}


def _suggestion_view(dishes: list[Dish]):
    text = (
        "<b>Сегодня можно приготовить:</b>\n"
        + "\n".join(f"• {escape(dish.name)}" for dish in dishes[:PAGE_SIZE])
        if dishes
        else "Каталог пока пуст."
    )
    rows = [[(dish.name, f"dish:view:{dish.id}")] for dish in dishes[:PAGE_SIZE]]
    rows.append([("🔄 Другие варианты", "suggest:more"), ("⭐ Избранное", "catalog:favorites")])
    return text, buttons(rows)


def _recommendation_view(results: list[Recommendation], page: int):
    rows = [[(item.dish.name, f"dish:view:{item.dish.id}")] for item in results[:PAGE_SIZE]]
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append((PREVIOUS_PAGE_LABEL, f"rec:results:{page - 1}"))
    if len(results) > PAGE_SIZE:
        nav.append((NEXT_PAGE_LABEL, f"rec:results:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔄 Новый подбор", "rec:start"), ("❌ Отмена", "flow:cancel")])
    return recommendation_text(results[:PAGE_SIZE]), buttons(rows)


@router.message(F.text == "🍽 Подобрать по продуктам")
@router.callback_query(F.data == "rec:start")
async def recommend_start(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(
                "Какой тип блюда нужен?", reply_markup=meal_types("rec:type", True)
            )
    else:
        await event.answer("Какой тип блюда нужен?", reply_markup=meal_types("rec:type", True))


@router.callback_query(F.data.startswith("rec:type:"))
async def recommend_type(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    value = callback.data.rsplit(":", 1)[-1]
    await state.set_state(Recommend.extras)
    await state.update_data(rec_type=value, selected_ids=[], pending_missing=[])
    frequent = await repository.quick_ingredients(
        callback.from_user.id, "frequent", limit=PAGE_SIZE + 1
    )
    quick_kind = "frequent" if frequent else None
    if not frequent:
        frequent = await repository.list_ingredients(limit=PAGE_SIZE)
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(MEAL_CHOICE_LABELS[value])
        await callback.message.answer(
            f"Введите продукты сообщением — <b>{LIST_INPUT_HINT}</b>. "
            "Можно указать один или несколько продуктов либо выбрать их кнопками.\n\n"
            "Быстрые продукты ниже ещё не выбраны. Выбранные будут отмечены ✅.",
            reply_markup=ingredient_picker(frequent, set(), "rec", quick_kind=quick_kind),
        )


@router.callback_query(Recommend.extras, F.data.startswith("rec:cat:"))
async def recommend_category(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    category = callback.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    ingredients = await repository.list_ingredients(category=category, limit=PAGE_SIZE + 1)
    category_name = dict(await repository.list_categories()).get(category, "Категория")
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(
            category_name,
            reply_markup=ingredient_picker(
                ingredients,
                set(data.get("selected_ids", [])),
                "rec",
                category=category,
            ),
        )


@router.callback_query(Recommend.extras, F.data.startswith("rec:ingredients:"))
async def recommend_ingredients_page(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    _, _, category, page_value = (callback.data or "").split(":", 3)
    page = max(0, int(page_value))
    ingredients = await repository.list_ingredients(
        category=category, limit=PAGE_SIZE + 1, offset=page * PAGE_SIZE
    )
    selected = set((await state.get_data()).get("selected_ids", []))
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_reply_markup(
            reply_markup=ingredient_picker(
                ingredients, selected, "rec", page=page, category=category
            )
        )


@router.callback_query(Recommend.extras, F.data.startswith("rec:quick:"))
async def recommend_quick(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    kind = callback.data.rsplit(":", 1)[-1]
    ingredients = await repository.quick_ingredients(
        callback.from_user.id, kind, limit=PAGE_SIZE + 1
    )
    await callback.answer()
    if callback.message:
        if not ingredients:
            await callback.message.answer("Этот быстрый список пока пуст.")
        elif not isinstance(callback.message, InaccessibleMessage):
            await callback.message.edit_text(
                _QUICK_LABELS[kind],
                reply_markup=ingredient_picker(
                    ingredients,
                    set((await state.get_data()).get("selected_ids", [])),
                    "rec",
                    quick_kind=kind,
                ),
            )


@router.callback_query(Recommend.extras, F.data.startswith("rec:quick_page:"))
async def recommend_quick_page(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    _, _, kind, page_value = (callback.data or "").split(":", 3)
    page = max(0, int(page_value))
    ingredients = await repository.quick_ingredients(
        callback.from_user.id,
        kind,
        limit=PAGE_SIZE + 1,
        offset=page * PAGE_SIZE,
    )
    selected = set((await state.get_data()).get("selected_ids", []))
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_reply_markup(
            reply_markup=ingredient_picker(ingredients, selected, "rec", page=page, quick_kind=kind)
        )


@router.callback_query(Recommend.extras, F.data.startswith("rec:ing:"))
async def recommend_toggle(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    ingredient_id = int(callback.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    selected.symmetric_difference_update({ingredient_id})
    await state.update_data(selected_ids=sorted(selected))
    names = [item.name for item in await repository.get_ingredients(selected)]
    await callback.answer("Выбор обновлён")
    if callback.message:
        await callback.message.answer(
            selected_text(names),
            reply_markup=buttons(
                [
                    [("➕ Добавить ещё", "rec:more"), ("🗑 Очистить продукты", "rec:clear")],
                    [("✅ Показать блюда", "rec:done"), ("❌ Отмена", "flow:cancel")],
                ]
            ),
        )


@router.message(Recommend.extras, F.text)
async def recommend_extra_text(
    message: Message, state: FSMContext, service: MealService, repository: AppRepository
) -> None:
    resolved, missing = await service.parse_ingredients(message.text or "")
    data = await state.get_data()
    selected = set(data.get("selected_ids", [])) | {item.id for item in resolved}
    await state.update_data(selected_ids=sorted(selected), pending_missing=missing)
    names = [item.name for item in await repository.get_ingredients(selected)]
    rows = [
        [("➕ Ещё", "rec:more"), ("🗑 Очистить продукты", "rec:clear")],
        [("✅ Показать блюда", "rec:done"), ("❌ Отмена", "flow:cancel")],
    ]
    if missing:
        rows.insert(
            0,
            [
                ("✅ Создать отсутствующие", "rec:create_missing"),
                ("❌ Пропустить", "rec:discard_missing"),
            ],
        )

    await message.answer(
        selected_text(names)
        + (
            "\nНе найдены: " + ", ".join(escape(name) for name in missing[:PAGE_SIZE])
            if missing
            else ""
        ),
        reply_markup=buttons(rows),
    )


@router.callback_query(Recommend.extras, F.data == "rec:create_missing")
async def recommend_create_missing(
    callback: CallbackQuery, state: FSMContext, service: MealService
) -> None:
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    for name in data.get("pending_missing", []):
        selected.add((await service.create_ingredient(callback.from_user.id, name)).id)
    await state.update_data(selected_ids=sorted(selected), pending_missing=[])
    await callback.answer("Добавлено")
    if callback.message:
        await callback.message.answer(
            "Ингредиенты добавлены. Нажмите «Показать блюда».",
            reply_markup=buttons(
                [
                    [("➕ Ещё", "rec:more"), ("🗑 Очистить продукты", "rec:clear")],
                    [("✅ Показать блюда", "rec:done"), ("❌ Отмена", "flow:cancel")],
                ]
            ),
        )


@router.callback_query(Recommend.extras, F.data == "rec:discard_missing")
async def recommend_discard(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(pending_missing=[])
    await callback.answer("Неизвестные продукты пропущены")
    if callback.message:
        await callback.message.answer(
            "Продолжайте выбор или нажмите «Показать блюда».",
            reply_markup=buttons(
                [
                    [("➕ Ещё", "rec:more"), ("🗑 Очистить продукты", "rec:clear")],
                    [("✅ Показать блюда", "rec:done"), ("❌ Отмена", "flow:cancel")],
                ]
            ),
        )


@router.callback_query(Recommend.extras, F.data == "rec:clear")
async def recommend_clear(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(selected_ids=[], pending_missing=[])
    await callback.answer("Продукты очищены")
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(
            f"Выбор продуктов очищен. Введите новый список {LIST_INPUT_HINT}.\n\n"
            "Быстрые продукты можно вернуть отдельной кнопкой.",
            reply_markup=empty_ingredient_picker("rec"),
        )


@router.callback_query(Recommend.extras, F.data == "rec:more")
async def recommend_more(callback: CallbackQuery, repository: AppRepository) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Добавьте продукты кнопками или отправьте список {LIST_INPUT_HINT}:",
            reply_markup=category_picker(
                await repository.list_categories(), "rec", include_quick=False
            ),
        )


@router.callback_query(Recommend.extras, F.data.startswith("rec:categories:"))
async def recommend_categories_page(callback: CallbackQuery, repository: AppRepository) -> None:
    page = max(0, int((callback.data or "").rsplit(":", 1)[-1]))
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(
            f"Добавьте продукты кнопками или отправьте список {LIST_INPUT_HINT}:",
            reply_markup=category_picker(
                await repository.list_categories(), "rec", page=page, include_quick=False
            ),
        )


@router.callback_query(Recommend.extras, F.data == "rec:back")
async def recommend_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Какой тип блюда нужен?", reply_markup=meal_types("rec:type", True)
        )


@router.callback_query(Recommend.extras, F.data == "rec:done")
async def recommend_done(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    if not selected_ids:
        await callback.answer("Сначала выберите хотя бы один продукт", show_alert=True)
        return
    meal_type = None if data.get("rec_type") == "any" else MealType(data["rec_type"])
    results = await service.recommend(
        callback.from_user.id, selected_ids, None, meal_type, limit=PAGE_SIZE + 1
    )
    await state.update_data(rec_result_page=0)
    await callback.answer()
    if callback.message:
        text, markup = _recommendation_view(results, 0)
        await callback.message.answer(text, reply_markup=markup)


@router.callback_query(Recommend.extras, F.data.startswith("rec:results:"))
async def recommend_results_page(
    callback: CallbackQuery, state: FSMContext, service: MealService
) -> None:
    page = max(0, int((callback.data or "").rsplit(":", 1)[-1]))
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    meal_type = None if data.get("rec_type") == "any" else MealType(data["rec_type"])
    results = await service.recommend(
        callback.from_user.id,
        selected_ids,
        None,
        meal_type,
        limit=PAGE_SIZE + 1,
        offset=page * PAGE_SIZE,
        record_usage=False,
    )
    await state.update_data(rec_result_page=page)
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        text, markup = _recommendation_view(results, page)
        await callback.message.edit_text(text, reply_markup=markup)


@router.message(F.text == "🎲 Что приготовить?")
async def suggest_start_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Какой тип блюда предложить?", reply_markup=meal_types("suggest:type", True)
    )


@router.callback_query(F.data.startswith("suggest:type:"))
async def suggest_type(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    value = callback.data.rsplit(":", 1)[-1]
    meal_type = None if value == "any" else MealType(value)
    dishes = await service.suggest(callback.from_user.id, meal_type, limit=PAGE_SIZE)
    await state.update_data(suggest_type=value, suggest_seen=[d.id for d in dishes])
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(MEAL_CHOICE_LABELS[value])
        text, markup = _suggestion_view(dishes)
        await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "suggest:more")
async def suggest_more(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    data = await state.get_data()
    value = data.get("suggest_type", "any")
    meal_type = None if value == "any" else MealType(value)
    dishes = await service.suggest(
        callback.from_user.id,
        meal_type,
        data.get("suggest_seen", []),
        limit=PAGE_SIZE,
    )
    seen = list(dict.fromkeys([*data.get("suggest_seen", []), *(dish.id for dish in dishes)]))
    await state.update_data(suggest_seen=seen)
    await callback.answer()
    if callback.message:
        text, markup = _suggestion_view(dishes)
        await callback.message.answer(text, reply_markup=markup)
