from types import SimpleNamespace
from unittest.mock import AsyncMock

from what_to_eat_bot.domain.models import Dish, Ingredient, MealType, Recommendation
from what_to_eat_bot.handlers import add_dish, catalog, recommend
from what_to_eat_bot.handlers.keyboards import (
    MAIN_MENU,
    category_picker,
    dish_card,
    dish_list,
    ingredient_picker,
    meal_types,
)


def _callback(data: str, user_id: int = 1):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            answer=AsyncMock(),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
        ),
        answer=AsyncMock(),
    )


def _dish(index: int, name: str | None = None) -> Dish:
    value = name or f"Блюдо {index}"
    return Dish(index, 1, "Тест", value, value.casefold(), MealType.MAIN)


def _rows(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def _callbacks(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_meal_type_labels_and_grouping_are_consistent() -> None:
    assert _rows(meal_types("suggest:type", include_all=True)) == [
        ["☕️ Завтрак", "🍗 Обед/ужин"],
        ["🍽️ Все блюда"],
        ["❌ Отмена"],
    ]


def test_main_menu_uses_books_emoji_for_catalog() -> None:
    labels = [[button.text for button in row] for row in MAIN_MENU.keyboard]
    assert "📚 Мои блюда" in labels[1]
    assert "📖 Мои блюда" not in labels[1]


def test_dish_card_does_not_offer_use_for_selection() -> None:
    callbacks = _callbacks(dish_card(_dish(1), viewer_id=1))
    assert not any(value.startswith("dish:use:") for value in callbacks)


def test_add_category_picker_has_no_frequent_or_recent_shortcuts() -> None:
    categories = [(f"category-{index}", f"Категория {index}") for index in range(1, 7)]
    markup = category_picker(categories, "add", include_quick=False)
    labels = [label for row in _rows(markup) for label in row]
    assert all(
        "Частые" not in label and "Недавние" not in label and "Избранные продукты" not in label
        for label in labels
    )
    assert len([label for label in labels if label.startswith("Категория")]) == 5
    assert "add:categories:1" in _callbacks(markup)


def test_dish_list_renders_only_five_items_and_navigation() -> None:
    markup = dish_list([_dish(index) for index in range(1, 7)], page=0)
    labels = [label for row in _rows(markup) for label in row]
    assert [label for label in labels if label.startswith("Блюдо")] == [
        "Блюдо 1",
        "Блюдо 2",
        "Блюдо 3",
        "Блюдо 4",
        "Блюдо 5",
    ]
    assert "catalog:page:1" in _callbacks(markup)
    assert "⏩ Вперед" in _rows(markup)[-2]


def test_pagination_buttons_have_explicit_navigation_labels() -> None:
    ingredients = [
        Ingredient(index, f"Ингредиент {index}", f"ингредиент {index}", "vegetables")
        for index in range(1, 7)
    ]
    category_markup = ingredient_picker(ingredients, set(), "add", category="vegetables")
    assert _rows(category_markup)[-3] == ["⏩ Вперед"]

    previous_markup = ingredient_picker(
        ingredients[:1], set(), "add", page=1, category="vegetables"
    )
    assert _rows(previous_markup)[-3] == ["⏪ Назад"]

    categories_markup = category_picker(
        [(f"category-{index}", f"Категория {index}") for index in range(1, 7)],
        "add",
        page=1,
        include_quick=False,
    )
    assert _rows(categories_markup)[-2] == ["⏪ Назад"]


def test_ingredient_page_renders_five_items_and_next_page() -> None:
    ingredients = [
        Ingredient(index, f"Ингредиент {index}", f"ингредиент {index}", "vegetables")
        for index in range(1, 7)
    ]
    markup = ingredient_picker(ingredients, set(), "add", category="vegetables")
    labels = [label for row in _rows(markup) for label in row]
    assert len([label for label in labels if label.startswith("Ингредиент")]) == 5
    assert "add:ingredients:vegetables:1" in _callbacks(markup)
    assert "add:categories:0" in _callbacks(markup)


async def test_recommend_more_shows_only_ingredient_categories() -> None:
    callback = _callback("rec:more")
    repository = SimpleNamespace(
        list_categories=AsyncMock(
            return_value=[
                ("meat", "🥩 Мясо"),
                ("vegetables", "🥕 Овощи"),
            ]
        )
    )

    await recommend.recommend_more(callback, repository)

    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    labels = [label for row in _rows(markup) for label in row]
    assert labels[:2] == ["🥩 Мясо", "🥕 Овощи"]
    assert all(
        shortcut not in labels for shortcut in ("🔥 Частые", "🕘 Недавние", "⭐ Избранные продукты")
    )


def test_quick_ingredient_page_has_navigation_and_returns_to_categories() -> None:
    ingredients = [
        Ingredient(index, f"Ингредиент {index}", f"ингредиент {index}", "other")
        for index in range(1, 7)
    ]
    markup = ingredient_picker(ingredients, set(), "add", quick_kind="favorite")
    callbacks = _callbacks(markup)
    assert "add:quick_page:favorite:1" in callbacks
    assert "add:categories:0" in callbacks


async def test_catalog_filter_keeps_visible_choice_but_pagination_does_not() -> None:
    callback = _callback("catalog:type:any")
    state = SimpleNamespace(update_data=AsyncMock())
    repository = SimpleNamespace(list_dishes=AsyncMock(return_value=[_dish(1)]))

    await catalog.catalog_type(callback, state, repository)

    callback.message.edit_text.assert_awaited_once_with("🍽️ Все блюда")
    callback.message.answer.assert_awaited_once()

    page_callback = _callback("catalog:page:1")
    page_state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={"catalog_type": "any", "catalog_favorites": False, "catalog_query": None}
        )
    )
    await catalog.catalog_page(page_callback, page_state, repository)

    page_callback.message.edit_reply_markup.assert_awaited_once()
    page_callback.message.edit_text.assert_not_awaited()
    page_callback.message.answer.assert_not_awaited()


async def test_suggestion_refresh_uses_same_heading_and_keyboard_shape() -> None:
    dishes = [_dish(1, "Омлет"), _dish(2, "Паста")]
    service = SimpleNamespace(suggest=AsyncMock(return_value=dishes))

    initial = _callback("suggest:type:any")
    initial_state = SimpleNamespace(update_data=AsyncMock())
    await recommend.suggest_type(initial, initial_state, service)

    refreshed = _callback("suggest:more")
    refreshed_state = SimpleNamespace(
        get_data=AsyncMock(return_value={"suggest_type": "any", "suggest_seen": [99]}),
        update_data=AsyncMock(),
    )
    await recommend.suggest_more(refreshed, refreshed_state, service)

    initial_call = initial.message.answer.await_args
    refreshed_call = refreshed.message.answer.await_args
    assert initial_call.args[0] == refreshed_call.args[0]
    assert initial_call.args[0].startswith("<b>Сегодня можно приготовить:</b>")
    assert _rows(initial_call.kwargs["reply_markup"]) == _rows(
        refreshed_call.kwargs["reply_markup"]
    )


async def test_recommendation_results_are_paginated_by_five() -> None:
    recommendations = [Recommendation(_dish(index), float(index), (), ()) for index in range(1, 7)]
    callback = _callback("rec:done")
    state = SimpleNamespace(
        get_data=AsyncMock(return_value={"selected_ids": [1], "rec_type": "any"}),
        update_data=AsyncMock(),
    )
    service = SimpleNamespace(
        recommend=AsyncMock(side_effect=[recommendations, recommendations[5:]])
    )

    await recommend.recommend_done(callback, state, service)

    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    callbacks = _callbacks(markup)
    assert len([value for value in callbacks if value.startswith("dish:view:")]) == 5
    assert "rec:results:1" in callbacks

    page_callback = _callback("rec:results:1")
    await recommend.recommend_results_page(page_callback, state, service)

    assert service.recommend.await_args.kwargs["offset"] == 5
    page_callback.message.edit_text.assert_awaited_once()


async def test_add_more_prompt_describes_newline_and_comma_input() -> None:
    callback = _callback("add:more")
    repository = SimpleNamespace(list_categories=AsyncMock(return_value=[]))

    await add_dish.add_more(callback, repository)

    prompt = callback.message.answer.await_args.args[0]
    assert "Enter" in prompt
    assert "запят" in prompt
    assert "flow:cancel" in _callbacks(callback.message.answer.await_args.kwargs["reply_markup"])


async def test_add_confirmation_uses_requested_three_row_footer() -> None:
    callback = _callback("add:done")
    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                "dish_name": "Омлет",
                "meal_type": "breakfast",
                "selected_ids": [1],
            }
        ),
        set_state=AsyncMock(),
    )
    repository = SimpleNamespace(
        get_ingredients=AsyncMock(return_value=[Ingredient(1, "Яйца", "яйца", "eggs")])
    )

    await add_dish.add_done(callback, state, repository)

    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    assert _rows(markup) == [
        ["✏️ Изменить название"],
        ["🔄 Изменить тип", "🥕 Изменить ингредиенты"],
        ["✅ Сохранить", "❌ Отмена"],
    ]
    assert "☕️ Завтрак" in callback.message.answer.await_args.args[0]
