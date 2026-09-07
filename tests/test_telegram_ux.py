from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from what_to_eat_bot.domain.models import (
    Dish,
    FamilyMealProposal,
    FamilyProposalRecipient,
    Ingredient,
    MealType,
    ProposalStatus,
    Recommendation,
)
from what_to_eat_bot.handlers import add_dish, catalog, family_proposals, recommend
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


def test_author_dish_card_uses_approved_family_proposal_layout() -> None:
    assert _rows(dish_card(_dish(1), viewer_id=1)) == [
        ["✏️ Редактировать", "⭐ В избранное"],
        ["😋 Предложить семье", "🗑 Удалить"],
        ["✅ Приготовил", "⬅️ К каталогу"],
    ]


def test_family_member_can_propose_another_members_dish() -> None:
    dish = Dish(1, 2, "Другой", "Блюдо", "блюдо", MealType.MAIN)
    assert _rows(dish_card(dish, viewer_id=1)) == [
        ["⭐ В избранное", "😋 Предложить семье"],
        ["✅ Приготовил", "⬅️ К каталогу"],
    ]


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


def _proposal(*, status: ProposalStatus = ProposalStatus.OPEN) -> FamilyMealProposal:
    accepted = True if status is ProposalStatus.AGREED else None
    return FamilyMealProposal(
        id=7,
        family_id=10,
        dish_id=42,
        proposer_id=1,
        proposer_name="Алексей",
        dish_name="Жареные пельмени",
        meal_type=MealType.MAIN,
        ingredient_names=("Пельмени",),
        status=status,
        expires_at=datetime(2026, 1, 2, tzinfo=UTC),
        recipients=(
            FamilyProposalRecipient(2, "Мария", accepted, 101 if accepted is not None else None),
            FamilyProposalRecipient(3, "Иван", accepted, 102 if accepted is not None else None),
        ),
    )


async def test_family_proposal_confirmation_uses_approved_copy_and_buttons() -> None:
    callback = _callback("dish:propose:42")
    repository = SimpleNamespace(
        get_dish=AsyncMock(return_value=_dish(42, "Жареные пельмени")),
        family_info=AsyncMock(return_value=(10, "Дом", [(1, "Алексей"), (2, "Мария")])),
    )

    await family_proposals.propose_prompt(callback, repository)

    prompt = callback.message.answer.await_args.args[0]
    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    assert "Жареные пельмени" in prompt
    assert _rows(markup) == [["✅ Да, отправить", "❌ Отмена"]]


async def test_family_proposal_is_sent_to_every_other_member() -> None:
    callback = _callback("proposal:send:42")
    callback.message.message_id = 500
    proposal = _proposal()
    service = SimpleNamespace(
        create_family_proposal=AsyncMock(return_value=proposal),
        record_family_proposal_message=AsyncMock(),
        record_family_proposal_sender_message=AsyncMock(),
        get_family_proposal=AsyncMock(return_value=proposal),
    )
    bot = SimpleNamespace(
        send_message=AsyncMock(
            side_effect=[SimpleNamespace(message_id=101), SimpleNamespace(message_id=102)]
        )
    )

    await family_proposals.send_proposal(callback, bot, service)

    assert [call.args[0] for call in bot.send_message.await_args_list] == [2, 3]
    recipient_text = bot.send_message.await_args_list[0].args[1]
    recipient_markup = bot.send_message.await_args_list[0].kwargs["reply_markup"]
    assert "Согласны приготовить это блюдо?" in recipient_text
    assert _rows(recipient_markup) == [["✅ Согласен(на)", "❌ Не согласен(на)"]]
    assert service.record_family_proposal_message.await_count == 2
    service.record_family_proposal_sender_message.assert_awaited_once_with(7, 1, 500)
    sender_text = callback.message.edit_text.await_args.args[0]
    assert "Ответили: 0 из 2" in sender_text


async def test_repeated_send_resumes_only_undelivered_recipients() -> None:
    callback = _callback("proposal:send:42")
    proposal = replace(
        _proposal(),
        recipients=(
            FamilyProposalRecipient(2, "Мария", message_id=101),
            FamilyProposalRecipient(3, "Иван"),
        ),
    )
    service = SimpleNamespace(
        create_family_proposal=AsyncMock(return_value=proposal),
        record_family_proposal_message=AsyncMock(),
        get_family_proposal=AsyncMock(return_value=proposal),
    )
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=102)))

    await family_proposals.send_proposal(callback, bot, service)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 3
    service.record_family_proposal_message.assert_awaited_once_with(7, 3, 102)


async def test_send_race_renders_completed_state_after_fast_last_vote() -> None:
    callback = _callback("proposal:send:42")
    open_proposal = _proposal()
    agreed_proposal = _proposal(status=ProposalStatus.AGREED)
    service = SimpleNamespace(
        create_family_proposal=AsyncMock(return_value=open_proposal),
        record_family_proposal_message=AsyncMock(),
        get_family_proposal=AsyncMock(return_value=agreed_proposal),
    )
    bot = SimpleNamespace(
        send_message=AsyncMock(
            side_effect=[SimpleNamespace(message_id=101), SimpleNamespace(message_id=102)]
        ),
        edit_message_reply_markup=AsyncMock(),
    )

    await family_proposals.send_proposal(callback, bot, service)

    assert "Договорились" in callback.message.edit_text.await_args.args[0]
    assert callback.message.edit_text.await_args.kwargs["reply_markup"] is None
    assert bot.edit_message_reply_markup.await_count == 2


async def test_last_positive_vote_notifies_everyone_and_closes_buttons() -> None:
    callback = _callback("proposal:vote:7:yes", user_id=3)
    proposal = replace(_proposal(status=ProposalStatus.AGREED), proposer_message_id=200)
    service = SimpleNamespace(respond_to_family_proposal=AsyncMock(return_value=(proposal, True)))
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        edit_message_text=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )

    await family_proposals.vote_proposal(callback, bot, service)

    assert callback.message.edit_text.await_args.kwargs["reply_markup"] is None
    assert "Ваш ответ: <b>✅ Согласен(на)</b>" in callback.message.edit_text.await_args.args[0]
    assert bot.edit_message_reply_markup.await_count == 2
    final_calls = [
        call for call in bot.send_message.await_args_list if "Договорились" in call.args[1]
    ]
    assert [call.args[0] for call in final_calls] == [2, 3]
    assert bot.edit_message_text.await_args.kwargs["message_id"] == 200
    assert (
        "<b>Согласны:</b>\n• Алексей\n• Мария\n• Иван"
        in bot.edit_message_text.await_args.kwargs["text"]
    )


async def test_expiration_closes_all_buttons_and_notifies_family() -> None:
    proposal = replace(
        _proposal(status=ProposalStatus.EXPIRED),
        proposer_message_id=200,
        recipients=(
            FamilyProposalRecipient(2, "Мария", message_id=101),
            FamilyProposalRecipient(3, "Иван", message_id=102),
        ),
    )
    service = SimpleNamespace(expire_family_proposals=AsyncMock(return_value=[proposal]))
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        edit_message_text=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )

    processed = await family_proposals.process_expired_proposals(
        bot,
        service,  # type: ignore[arg-type]
    )

    assert processed == 1
    assert bot.edit_message_reply_markup.await_count == 2
    assert bot.edit_message_text.await_args.kwargs["message_id"] == 200
    assert [call.args[0] for call in bot.send_message.await_args_list] == [1, 2, 3]
    assert all("больше неактуально" in call.args[1] for call in bot.send_message.await_args_list)
