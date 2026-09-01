from collections.abc import Iterable, Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from what_to_eat_bot.domain.models import Dish, Ingredient
from what_to_eat_bot.handlers.presentation import (
    ALL_DISHES_LABEL,
    BREAKFAST_LABEL,
    MAIN_LABEL,
    NEXT_PAGE_LABEL,
    PAGE_SIZE,
    PREVIOUS_PAGE_LABEL,
)

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🍽 Подобрать по продуктам"),
            KeyboardButton(text="🎲 Что приготовить?"),
        ],
        [KeyboardButton(text="📚 Мои блюда"), KeyboardButton(text="➕ Добавить блюдо")],
        [KeyboardButton(text="⭐ Избранное"), KeyboardButton(text="⚙️ Настройки")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)


def buttons(rows: Sequence[Sequence[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def onboarding() -> InlineKeyboardMarkup:
    return buttons(
        [
            [("➕ Добавить первое блюдо", "add:start")],
            [("ℹ️ Как это работает", "help:how")],
        ]
    )


def meal_types(prefix: str, include_all: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            (BREAKFAST_LABEL, f"{prefix}:breakfast"),
            (MAIN_LABEL, f"{prefix}:main"),
        ]
    ]
    if include_all:
        rows.append([(ALL_DISHES_LABEL, f"{prefix}:any")])
    rows.append([("❌ Отмена", "flow:cancel")])
    return buttons(rows)


def dish_list(dishes: Sequence[Dish], page: int, prefix: str = "dish") -> InlineKeyboardMarkup:
    rows = [[(dish.name, f"{prefix}:view:{dish.id}")] for dish in dishes[:PAGE_SIZE]]
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append((PREVIOUS_PAGE_LABEL, f"catalog:page:{page - 1}"))
    if len(dishes) > PAGE_SIZE:
        nav.append((NEXT_PAGE_LABEL, f"catalog:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("⬅️ Категории", "catalog:root"), ("❌ Отмена", "flow:cancel")])
    return buttons(rows)


def dish_card(dish: Dish, viewer_id: int) -> InlineKeyboardMarkup:
    favorite = "☆ Убрать из избранного" if dish.is_favorite else "⭐ В избранное"
    rows: list[list[tuple[str, str]]] = [
        [(favorite, f"dish:fav:{dish.id}"), ("✅ Приготовил", f"dish:cooked:{dish.id}")],
    ]
    if dish.author_id == viewer_id:
        rows.append(
            [("✏️ Редактировать", f"dish:edit:{dish.id}"), ("🗑 Удалить", f"dish:delete:{dish.id}")]
        )
    rows.append([("⬅️ К каталогу", "catalog:root")])
    return buttons(rows)


def ingredient_picker(
    ingredients: Iterable[Ingredient],
    selected: set[int],
    prefix: str,
    *,
    page: int = 0,
    category: str | None = None,
    quick_kind: str | None = None,
) -> InlineKeyboardMarkup:
    all_ingredients = list(ingredients)
    rows = []
    for ingredient in all_ingredients[:PAGE_SIZE]:
        marker = "✅ " if ingredient.id in selected else ""
        rows.append([(f"{marker}{ingredient.name}", f"{prefix}:ing:{ingredient.id}")])
    if category is not None:
        nav: list[tuple[str, str]] = []
        if page > 0:
            nav.append((PREVIOUS_PAGE_LABEL, f"{prefix}:ingredients:{category}:{page - 1}"))
        if len(all_ingredients) > PAGE_SIZE:
            nav.append((NEXT_PAGE_LABEL, f"{prefix}:ingredients:{category}:{page + 1}"))
        if nav:
            rows.append(nav)
    elif quick_kind is not None:
        nav = []
        if page > 0:
            nav.append((PREVIOUS_PAGE_LABEL, f"{prefix}:quick_page:{quick_kind}:{page - 1}"))
        if len(all_ingredients) > PAGE_SIZE:
            nav.append((NEXT_PAGE_LABEL, f"{prefix}:quick_page:{quick_kind}:{page + 1}"))
        if nav:
            rows.append(nav)
    back_callback = (
        f"{prefix}:categories:0"
        if category is not None or quick_kind is not None
        else f"{prefix}:back"
    )
    rows.extend(
        [
            [
                ("🗑 Очистить продукты", f"{prefix}:clear"),
                ("⬅️ Назад", back_callback),
            ],
            [("✅ Готово", f"{prefix}:done"), ("❌ Отмена", "flow:cancel")],
        ]
    )
    return buttons(rows)


def empty_ingredient_picker(prefix: str) -> InlineKeyboardMarkup:
    return buttons(
        [
            [
                ("🔥 Показать быстрые продукты", f"{prefix}:quick:frequent"),
                ("⬅️ Назад", f"{prefix}:back"),
            ],
            [("✅ Готово", f"{prefix}:done"), ("❌ Отмена", "flow:cancel")],
        ]
    )


def category_picker(
    categories: Iterable[tuple[str, str]],
    prefix: str,
    *,
    page: int = 0,
    include_quick: bool = True,
) -> InlineKeyboardMarkup:
    all_categories = list(categories)
    start = page * PAGE_SIZE
    visible = all_categories[start : start + PAGE_SIZE]
    rows: list[list[tuple[str, str]]] = []
    for index in range(0, len(visible), 2):
        rows.append([(name, f"{prefix}:cat:{code}") for code, name in visible[index : index + 2]])
    if include_quick:
        rows.insert(
            0,
            [
                ("🔥 Частые", f"{prefix}:quick:frequent"),
                ("🕘 Недавние", f"{prefix}:quick:recent"),
            ],
        )
    if include_quick:
        rows.insert(1, [("⭐ Избранные продукты", f"{prefix}:quick:favorite")])
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append((PREVIOUS_PAGE_LABEL, f"{prefix}:categories:{page - 1}"))
    if start + PAGE_SIZE < len(all_categories):
        nav.append((NEXT_PAGE_LABEL, f"{prefix}:categories:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("✅ Готово", f"{prefix}:done"), ("❌ Отмена", "flow:cancel")])
    return buttons(rows)
