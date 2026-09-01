from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.handlers.keyboards import buttons, meal_types
from what_to_eat_bot.handlers.presentation import LIST_INPUT_HINT, PAGE_SIZE
from what_to_eat_bot.handlers.states import EditDish
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="edit_dish")


@router.callback_query(F.data.startswith("dish:edit:"))
async def edit_start(callback: CallbackQuery, state: FSMContext, repository: AppRepository) -> None:
    dish_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        dish = await repository.get_dish(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    if dish.author_id != callback.from_user.id:
        await callback.answer("Редактировать блюдо может только автор", show_alert=True)
        return
    await state.set_state(EditDish.menu)
    await state.update_data(
        edit_id=dish.id,
        edit_name=dish.name,
        edit_type=dish.meal_type.value,
        edit_ingredients=[item.id for item in dish.ingredients],
    )
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Что изменить?",
            reply_markup=buttons(
                [
                    [("✏️ Название", "edit:name"), ("🔄 Тип", "edit:type")],
                    [("🥕 Ингредиенты", "edit:ingredients")],
                    [("❌ Отмена", "flow:cancel")],
                ]
            ),
        )


@router.callback_query(EditDish.menu, F.data == "edit:name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditDish.name)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Введите новое название:", reply_markup=buttons([[("❌ Отмена", "flow:cancel")]])
        )


@router.message(EditDish.name, F.text)
async def edit_name_save(message: Message, state: FSMContext, service: MealService) -> None:
    if not message.from_user:
        return
    data = await state.get_data()
    try:
        await service.update_dish(
            message.from_user.id,
            data["edit_id"],
            message.text or "",
            MealType(data["edit_type"]),
            data["edit_ingredients"],
        )
    except DomainError as error:
        await message.answer(str(error), reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]))
        return
    await state.clear()
    await message.answer(
        "Название обновлено.",
        reply_markup=buttons([[("Открыть блюдо", f"dish:view:{data['edit_id']}")]]),
    )


@router.callback_query(EditDish.menu, F.data == "edit:type")
async def edit_type_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditDish.meal_type)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Выберите новый тип:", reply_markup=meal_types("edit:set_type")
        )


@router.callback_query(EditDish.meal_type, F.data.startswith("edit:set_type:"))
async def edit_type_save(callback: CallbackQuery, state: FSMContext, service: MealService) -> None:
    data = await state.get_data()
    meal_type = MealType(callback.data.rsplit(":", 1)[-1])
    try:
        await service.update_dish(
            callback.from_user.id,
            data["edit_id"],
            data["edit_name"],
            meal_type,
            data["edit_ingredients"],
        )
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    await callback.answer("Тип обновлён")
    if callback.message:
        await callback.message.answer(
            "Тип блюда обновлён.",
            reply_markup=buttons([[("Открыть блюдо", f"dish:view:{data['edit_id']}")]]),
        )


@router.callback_query(EditDish.menu, F.data == "edit:ingredients")
async def edit_ingredients_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditDish.ingredients)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Введите полный новый список ингредиентов {LIST_INPUT_HINT}. "
            "Сохранение заменит прежний список.",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )


@router.message(EditDish.ingredients, F.text)
async def edit_ingredients_parse(message: Message, state: FSMContext, service: MealService) -> None:
    resolved, missing = await service.parse_ingredients(message.text or "")
    await state.update_data(
        edit_new_ingredients=[item.id for item in resolved], edit_missing=missing
    )
    if missing:
        await message.answer(
            "Не найдены: "
            + ", ".join(escape(name) for name in missing[:PAGE_SIZE])
            + ". Создать их?",
            reply_markup=buttons(
                [
                    [
                        ("✅ Создать и сохранить", "edit:create_missing"),
                        ("✏️ Ввести заново", "edit:ingredients"),
                    ],
                    [("❌ Отмена", "flow:cancel")],
                ]
            ),
        )
    else:
        await message.answer(
            "Заменить список ингредиентов?",
            reply_markup=buttons(
                [[("✅ Сохранить", "edit:save_ingredients"), ("❌ Отмена", "flow:cancel")]]
            ),
        )


@router.callback_query(EditDish.ingredients, F.data == "edit:ingredients")
async def edit_ingredients_again(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Введите список заново {LIST_INPUT_HINT}:",
            reply_markup=buttons([[("❌ Отмена", "flow:cancel")]]),
        )


@router.callback_query(EditDish.ingredients, F.data == "edit:create_missing")
async def edit_create_missing(
    callback: CallbackQuery, state: FSMContext, service: MealService
) -> None:
    data = await state.get_data()
    ids = set(data.get("edit_new_ingredients", []))
    for name in data.get("edit_missing", []):
        ids.add((await service.create_ingredient(callback.from_user.id, name)).id)
    await state.update_data(edit_new_ingredients=sorted(ids), edit_missing=[])
    await callback.answer("Ингредиенты созданы")
    await _save_ingredients(callback, state, service)


@router.callback_query(EditDish.ingredients, F.data == "edit:save_ingredients")
async def edit_save_ingredients(
    callback: CallbackQuery, state: FSMContext, service: MealService
) -> None:
    await _save_ingredients(callback, state, service)


async def _save_ingredients(
    callback: CallbackQuery, state: FSMContext, service: MealService
) -> None:
    data = await state.get_data()
    try:
        await service.update_dish(
            callback.from_user.id,
            data["edit_id"],
            data["edit_name"],
            MealType(data["edit_type"]),
            data.get("edit_new_ingredients", []),
        )
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    await callback.answer("Ингредиенты обновлены")
    if callback.message:
        await callback.message.answer(
            "Ингредиенты обновлены.",
            reply_markup=buttons([[("Открыть блюдо", f"dish:view:{data['edit_id']}")]]),
        )
