from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic import ValidationError

from what_to_eat_bot import app as app_module
from what_to_eat_bot.config import Settings
from what_to_eat_bot.domain.models import Ingredient
from what_to_eat_bot.handlers import (
    add_dish,
    catalog,
    recommend,
    settings_family,
    start,
)
from what_to_eat_bot.handlers.keyboards import ingredient_picker


def message_mock(user_id: int = 1, text: str | None = None):
    user = SimpleNamespace(id=user_id, full_name="Тест", username="tester")
    return SimpleNamespace(from_user=user, text=text, answer=AsyncMock())


def callback_mock(data: str, user_id: int = 1):
    user = SimpleNamespace(id=user_id)
    message = SimpleNamespace(
        answer=AsyncMock(), edit_text=AsyncMock(), edit_reply_markup=AsyncMock()
    )
    return SimpleNamespace(data=data, from_user=user, message=message, answer=AsyncMock())


class InMemoryState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.state = None

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)

    async def update_data(self, **values: object) -> None:
        self.data.update(values)

    async def set_state(self, state: object) -> None:
        self.state = state

    async def clear(self) -> None:
        self.data.clear()
        self.state = None


async def test_start_onboards_empty_catalog_without_telegram_api() -> None:
    message = message_mock()
    state = SimpleNamespace(clear=AsyncMock())
    repository = SimpleNamespace(ensure_user=AsyncMock(), count_dishes=AsyncMock(return_value=0))
    await start.start(
        message,
        SimpleNamespace(args=None),
        state,
        repository,
        SimpleNamespace(),
    )
    repository.ensure_user.assert_awaited_once_with(1, "Тест", "tester")
    assert "добавь несколько блюд" in message.answer.await_args.args[0]


async def test_text_cancel_clears_any_waiting_fsm_state() -> None:
    message = message_mock(text=" ОТМЕНА ")
    state = SimpleNamespace(clear=AsyncMock())

    await start.cancel_text(message, state)

    state.clear.assert_awaited_once()
    assert message.answer.await_args.args[0] == "Действие отменено."


async def test_add_name_moves_fsm_to_type_selection() -> None:
    message = message_mock(text="Омлет")
    state = SimpleNamespace(update_data=AsyncMock(), set_state=AsyncMock())
    await add_dish.add_name(message, state)
    state.update_data.assert_awaited_once_with(dish_name="Омлет")
    state.set_state.assert_awaited_once()
    assert "Выберите тип" in message.answer.await_args.args[0]


async def test_delete_confirmation_is_idempotent() -> None:
    callback = callback_mock("dish:confirm_delete:42")
    repository = SimpleNamespace(delete_dish=AsyncMock(side_effect=[True, False]))
    await catalog.delete_confirm(callback, repository)
    await catalog.delete_confirm(callback, repository)
    assert repository.delete_dish.await_count == 2
    assert callback.message.edit_text.await_count == 1
    assert callback.answer.await_args_list[-1].kwargs["show_alert"] is True


async def test_recommendation_requires_at_least_one_product() -> None:
    callback = callback_mock("rec:done")
    state = SimpleNamespace(get_data=AsyncMock(return_value={}))
    service = SimpleNamespace(recommend=AsyncMock())
    await recommend.recommend_done(callback, state, service)
    service.recommend.assert_not_awaited()
    assert callback.answer.await_args.kwargs["show_alert"] is True


async def test_recommendation_starts_with_at_most_five_products_and_no_text_button() -> None:
    callback = callback_mock("rec:type:main")
    state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())
    ingredients = [
        Ingredient(index, f"Продукт {index}", f"продукт {index}", "other") for index in range(1, 9)
    ]
    repository = SimpleNamespace(
        quick_ingredients=AsyncMock(return_value=ingredients),
        list_ingredients=AsyncMock(),
    )

    await recommend.recommend_type(callback, state, repository)

    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:5] == [f"Продукт {index}" for index in range(1, 6)]
    assert len([label for label in labels if label.startswith("Продукт")]) == 5
    assert all("Ввести" not in label for label in labels)
    assert "🗑 Очистить продукты" in labels


async def test_recommendation_clear_removes_all_products() -> None:
    callback = callback_mock("rec:clear")
    state = SimpleNamespace(update_data=AsyncMock())

    await recommend.recommend_clear(callback, state)

    state.update_data.assert_awaited_once_with(selected_ids=[], pending_missing=[])
    assert "Выбор продуктов очищен" in callback.message.edit_text.await_args.args[0]
    markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "Сметана" not in labels
    assert "Курица" not in labels
    assert "🔥 Показать быстрые продукты" in labels


async def test_recommendation_selection_clear_and_done_flow() -> None:
    state = InMemoryState()
    ingredients = {
        1: Ingredient(1, "Сметана", "сметана", "dairy"),
        2: Ingredient(2, "Курица", "курица", "meat"),
    }
    repository = SimpleNamespace(
        quick_ingredients=AsyncMock(return_value=list(ingredients.values())),
        list_ingredients=AsyncMock(return_value=list(ingredients.values())),
        get_ingredients=AsyncMock(
            side_effect=lambda ids: [ingredients[item_id] for item_id in sorted(ids)]
        ),
    )

    await recommend.recommend_type(callback_mock("rec:type:main"), state, repository)
    await recommend.recommend_toggle(callback_mock("rec:ing:1"), state, repository)
    await recommend.recommend_toggle(callback_mock("rec:ing:2"), state, repository)
    assert state.data["selected_ids"] == [1, 2]

    clear_callback = callback_mock("rec:clear")
    await recommend.recommend_clear(clear_callback, state)
    assert state.data["selected_ids"] == []
    clear_markup = clear_callback.message.edit_text.await_args.kwargs["reply_markup"]
    assert all(
        not (button.callback_data or "").startswith("rec:ing:")
        for row in clear_markup.inline_keyboard
        for button in row
    )

    service = SimpleNamespace(recommend=AsyncMock())
    done_callback = callback_mock("rec:done")
    await recommend.recommend_done(done_callback, state, service)
    service.recommend.assert_not_awaited()
    assert done_callback.answer.await_args.kwargs["show_alert"] is True


async def test_text_product_selection_always_offers_clear() -> None:
    state = InMemoryState()
    state.data = {"rec_type": "main", "selected_ids": [], "pending_missing": []}
    ingredients = [
        Ingredient(1, "Сметана", "сметана", "dairy"),
        Ingredient(2, "Курица", "курица", "meat"),
    ]
    service = SimpleNamespace(parse_ingredients=AsyncMock(return_value=(ingredients, [])))
    repository = SimpleNamespace(get_ingredients=AsyncMock(return_value=ingredients))
    message = message_mock(text="Сметана\nКурица")

    await recommend.recommend_extra_text(message, state, service, repository)

    assert state.data["selected_ids"] == [1, 2]
    markup = message.answer.await_args.kwargs["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "rec:clear" in callbacks


def test_callback_data_is_below_telegram_limit() -> None:
    ingredients = [Ingredient(123456789, "Очень длинное имя", "имя", "other")]
    markup = ingredient_picker(ingredients, {123456789}, "rec")
    callback_values = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert max(map(len, callback_values)) <= 64


def test_config_requires_bot_token(monkeypatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    try:
        Settings(_env_file=None)  # type: ignore[call-arg]
    except ValidationError as error:
        assert error.errors()[0]["loc"] == ("BOT_TOKEN",)
    else:
        raise AssertionError("BOT_TOKEN must be required")


async def test_add_save_completes_fsm_without_telegram_api() -> None:
    callback = callback_mock("add:save")
    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                "dish_name": "Омлет",
                "meal_type": "breakfast",
                "selected_ids": [1],
            }
        ),
        clear=AsyncMock(),
    )
    service = SimpleNamespace(create_dish=AsyncMock(return_value=42))

    await add_dish.add_save(callback, state, service)

    service.create_dish.assert_awaited_once()
    state.clear.assert_awaited_once()
    callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    assert callback.message.answer.await_count == 2
    saved_call = callback.message.answer.await_args_list[0]
    assert saved_call.args[0] == "Блюдо сохранено. Теперь оно участвует в подборе."
    assert "reply_markup" not in saved_call.kwargs


async def test_recommend_success_completes_fsm_without_telegram_api() -> None:
    callback = callback_mock("rec:done")
    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                "selected_ids": [1, 2],
                "rec_type": "main",
            }
        ),
        clear=AsyncMock(),
        update_data=AsyncMock(),
    )
    service = SimpleNamespace(recommend=AsyncMock(return_value=[]))

    await recommend.recommend_done(callback, state, service)

    service.recommend.assert_awaited_once()
    state.clear.assert_not_awaited()
    state.update_data.assert_awaited_once_with(rec_result_page=0)
    callback.message.answer.assert_awaited_once()


async def test_family_join_completes_confirmation_fsm() -> None:
    callback = callback_mock("family:join")
    state = SimpleNamespace(
        get_data=AsyncMock(return_value={"invite_token": "opaque-token"}),
        clear=AsyncMock(),
    )
    service = SimpleNamespace(accept_family_invite=AsyncMock(return_value=7))

    await settings_family.family_join(callback, state, service)

    service.accept_family_invite.assert_awaited_once_with(1, "opaque-token")
    state.clear.assert_awaited_once()
    callback.message.edit_text.assert_awaited_once()


async def test_polling_shutdown_closes_session_without_closed_attribute(monkeypatch) -> None:
    session = SimpleNamespace(close=AsyncMock())
    bot = SimpleNamespace(session=session, delete_webhook=AsyncMock())
    dispatcher = SimpleNamespace(
        start_polling=AsyncMock(),
        resolve_used_update_types=lambda: [],
        storage=SimpleNamespace(close=AsyncMock()),
    )
    application = SimpleNamespace(bot=bot, dispatcher=dispatcher)
    monkeypatch.setattr(app_module, "create_application", AsyncMock(return_value=application))

    await app_module.run_polling(SimpleNamespace())

    session.close.assert_awaited_once()
