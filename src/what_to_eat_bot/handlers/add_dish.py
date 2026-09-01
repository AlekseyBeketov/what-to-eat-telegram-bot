from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, InlineKeyboardMarkup, Message

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.handlers.formatters import selected_text
from what_to_eat_bot.handlers.keyboards import (
    MAIN_MENU,
    buttons,
    category_picker,
    ingredient_picker,
    meal_types,
)
from what_to_eat_bot.handlers.presentation import (
    LIST_INPUT_HINT,
    MEAL_CHOICE_LABELS,
    MEAL_TYPE_LABELS,
    PAGE_SIZE,
)
from what_to_eat_bot.handlers.states import AddDish
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="add_dish")


def _selection_actions() -> InlineKeyboardMarkup:
    return buttons(
        [
            [("➕ Добавить ещё", "add:more"), ("🗑 Очистить", "add:clear")],
            [("✅ Готово", "add:done"), ("❌ Отмена", "flow:cancel")],
        ]
    )


def _category_prompt() -> str:
    return f"Выберите категорию или отправьте список {LIST_INPUT_HINT}:"


@router.message(F.text == "➕ Добавить блюдо")
@router.callback_query(F.data == "add:start")
async def add_start(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddDish.name)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(
                "Как называется блюдо?", reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
            )
    else:
        await event.answer(
            "Как называется блюдо?", reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
        )


@router.message(AddDish.name, F.text)
async def add_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(
            "Название слишком короткое. Введите ещё раз:",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )
        return
    await state.update_data(dish_name=name)
    await state.set_state(AddDish.meal_type)
    await message.answer("Выберите тип блюда:", reply_markup=meal_types("add:type"))


@router.callback_query(AddDish.meal_type, F.data.startswith("add:type:"))
async def add_type(callback: CallbackQuery, state: FSMContext, repository: AppRepository) -> None:
    meal_type = callback.data.rsplit(":", 1)[-1]
    current = await state.get_data()
    await state.update_data(
        meal_type=meal_type,
        selected_ids=current.get("selected_ids", []),
        pending_missing=[],
    )
    await state.set_state(AddDish.ingredients)
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        categories = await repository.list_categories()
        await callback.message.edit_text(MEAL_CHOICE_LABELS[meal_type])
        await callback.message.answer(
            f"Добавьте ингредиенты кнопками или отправьте список {LIST_INPUT_HINT}.\n\n"
            "<b>Выбрано: 0</b>",
            reply_markup=category_picker(categories, "add", include_quick=False),
        )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:cat:"))
async def add_category(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    category = callback.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    ingredients = await repository.list_ingredients(category=category, limit=PAGE_SIZE + 1)
    category_name = dict(await repository.list_categories()).get(category, "Категория")
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(
            category_name,
            reply_markup=ingredient_picker(ingredients, selected, "add", category=category),
        )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:ingredients:"))
async def add_ingredients_page(
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
                ingredients, selected, "add", page=page, category=category
            )
        )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:categories:"))
async def add_categories_page(callback: CallbackQuery, repository: AppRepository) -> None:
    page = max(0, int((callback.data or "").rsplit(":", 1)[-1]))
    await callback.answer()
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_text(
            _category_prompt(),
            reply_markup=category_picker(
                await repository.list_categories(), "add", page=page, include_quick=False
            ),
        )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:quick:"))
async def add_quick(callback: CallbackQuery, state: FSMContext, repository: AppRepository) -> None:
    kind = callback.data.rsplit(":", 1)[-1]
    ingredients = await repository.quick_ingredients(
        callback.from_user.id, kind, limit=PAGE_SIZE + 1
    )
    selected = set((await state.get_data()).get("selected_ids", []))
    await callback.answer()
    if callback.message:
        if not ingredients:
            await callback.message.answer("Этот быстрый список пока пуст.")
        elif not isinstance(callback.message, InaccessibleMessage):
            await callback.message.edit_text(
                "⭐ Избранные продукты",
                reply_markup=ingredient_picker(ingredients, selected, "add", quick_kind=kind),
            )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:quick_page:"))
async def add_quick_page(
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
            reply_markup=ingredient_picker(ingredients, selected, "add", page=page, quick_kind=kind)
        )


@router.callback_query(AddDish.ingredients, F.data.startswith("add:ing:"))
async def add_toggle(callback: CallbackQuery, state: FSMContext, repository: AppRepository) -> None:
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
            reply_markup=_selection_actions(),
        )


@router.callback_query(AddDish.ingredients, F.data == "add:more")
async def add_more(callback: CallbackQuery, repository: AppRepository) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            _category_prompt(),
            reply_markup=category_picker(
                await repository.list_categories(), "add", include_quick=False
            ),
        )


@router.callback_query(AddDish.ingredients, F.data == "add:text")
async def add_text_hint(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Отправьте ингредиенты {LIST_INPUT_HINT}, например:\nкурица\nлук\nморковь",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )


@router.message(AddDish.ingredients, F.text)
async def add_text(
    message: Message, state: FSMContext, service: MealService, repository: AppRepository
) -> None:
    resolved, missing = await service.parse_ingredients(message.text or "")
    data = await state.get_data()
    selected = set(data.get("selected_ids", [])) | {item.id for item in resolved}
    await state.update_data(selected_ids=sorted(selected), pending_missing=missing)
    names = [item.name for item in await repository.get_ingredients(selected)]
    if missing:
        unknown = ", ".join(escape(name) for name in missing[:PAGE_SIZE])
        await message.answer(
            selected_text(names) + f"\n\nНе найдено: {unknown}. Добавить как новые ингредиенты?",
            reply_markup=buttons(
                [
                    [
                        ("✅ Добавить новые", "add:create_missing"),
                        ("✏️ Ввести заново", "add:text"),
                    ],
                    [("Пропустить", "add:discard_missing"), ("❌ Отмена", "flow:cancel")],
                ]
            ),
        )
    else:
        await message.answer(
            selected_text(names),
            reply_markup=_selection_actions(),
        )


@router.callback_query(AddDish.ingredients, F.data == "add:create_missing")
async def add_create_missing(
    callback: CallbackQuery, state: FSMContext, service: MealService, repository: AppRepository
) -> None:
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    for name in data.get("pending_missing", []):
        ingredient = await service.create_ingredient(callback.from_user.id, name)
        selected.add(ingredient.id)
    await state.update_data(selected_ids=sorted(selected), pending_missing=[])
    names = [item.name for item in await repository.get_ingredients(selected)]
    await callback.answer("Ингредиенты добавлены")
    if callback.message:
        await callback.message.answer(
            selected_text(names),
            reply_markup=_selection_actions(),
        )


@router.callback_query(AddDish.ingredients, F.data == "add:discard_missing")
async def add_discard_missing(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(pending_missing=[])
    await callback.answer("Неизвестные ингредиенты пропущены")
    if callback.message:
        await callback.message.answer(
            "Продолжайте выбор или нажмите «Готово».", reply_markup=_selection_actions()
        )


@router.callback_query(AddDish.ingredients, F.data == "add:clear")
async def add_clear(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(selected_ids=[], pending_missing=[])
    await callback.answer("Список очищен")
    if callback.message:
        await callback.message.answer("<b>Выбрано: 0</b>", reply_markup=_selection_actions())


@router.callback_query(AddDish.ingredients, F.data == "add:back")
async def add_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddDish.meal_type)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите тип блюда:", reply_markup=meal_types("add:type"))


@router.callback_query(AddDish.ingredients, F.data == "add:done")
async def add_done(callback: CallbackQuery, state: FSMContext, repository: AppRepository) -> None:
    data = await state.get_data()
    selected = data.get("selected_ids", [])
    if not selected:
        await callback.answer("Добавьте хотя бы один ингредиент", show_alert=True)
        return
    await state.set_state(AddDish.confirm)
    ingredients = await repository.get_ingredients(selected)
    type_name = MEAL_TYPE_LABELS[MealType(data["meal_type"])]
    ingredient_text = "\n".join(f"• {escape(item.name)}" for item in ingredients[:PAGE_SIZE])
    if len(ingredients) > PAGE_SIZE:
        ingredient_text += f"\n… ещё {len(ingredients) - PAGE_SIZE}"
    text = f"<b>{escape(data['dish_name'])}</b>\nТип: {type_name}\n\n{ingredient_text}"
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=buttons(
                [
                    [("✏️ Изменить название", "add:edit_name")],
                    [
                        ("🔄 Изменить тип", "add:edit_type"),
                        ("🥕 Изменить ингредиенты", "add:edit_ingredients"),
                    ],
                    [("✅ Сохранить", "add:save"), ("❌ Отмена", "flow:cancel")],
                ]
            ),
        )


@router.callback_query(AddDish.confirm, F.data == "add:edit_name")
async def add_edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddDish.name)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Введите новое название:", reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
        )


@router.callback_query(AddDish.confirm, F.data == "add:edit_type")
async def add_edit_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddDish.meal_type)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите тип:", reply_markup=meal_types("add:type"))


@router.callback_query(AddDish.confirm, F.data == "add:edit_ingredients")
async def add_edit_ingredients(
    callback: CallbackQuery, state: FSMContext, repository: AppRepository
) -> None:
    await state.set_state(AddDish.ingredients)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Измените список ингредиентов — отправьте их "
            f"{LIST_INPUT_HINT} или выберите категорию:",
            reply_markup=category_picker(
                await repository.list_categories(), "add", include_quick=False
            ),
        )


@router.callback_query(AddDish.confirm, F.data == "add:save")
async def add_save(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    data = await state.get_data()
    try:
        await service.create_dish(
            callback.from_user.id,
            data["dish_name"],
            MealType(data["meal_type"]),
            data["selected_ids"],
        )
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    await callback.answer("Сохранено")
    if callback.message and not isinstance(callback.message, InaccessibleMessage):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Блюдо сохранено. Теперь оно участвует в подборе.")
        await callback.message.answer("Главное меню:", reply_markup=MAIN_MENU)
