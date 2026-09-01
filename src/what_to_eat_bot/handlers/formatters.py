from collections.abc import Sequence
from html import escape

from what_to_eat_bot.domain.models import Dish, Recommendation
from what_to_eat_bot.handlers.presentation import MEAL_TYPE_LABELS, PAGE_SIZE


def _limited_names(items: Sequence, separator: str) -> str:
    visible = separator.join(escape(item.name) for item in items[:PAGE_SIZE])
    if len(items) > PAGE_SIZE:
        visible += f"{separator}… ещё {len(items) - PAGE_SIZE}"
    return visible


def dish_text(dish: Dish) -> str:
    ingredients = _limited_names(dish.ingredients, "\n• ")
    if ingredients:
        ingredients = "• " + ingredients
    favorite = "⭐ " if dish.is_favorite else ""
    return (
        f"<b>{favorite}{escape(dish.name)}</b>\n"
        f"Тип: {MEAL_TYPE_LABELS[dish.meal_type]}\n"
        f"Добавил: {escape(dish.author_name)}\n\n"
        f"<b>Ингредиенты:</b>\n{ingredients}"
    )


def recommendation_text(items: list[Recommendation]) -> str:
    if not items:
        return "Подходящих блюд нет. Проверь выбранные продукты или добавь блюда в каталог."
    blocks = ["<b>Подходящие блюда:</b>"]
    for index, item in enumerate(items[:PAGE_SIZE], 1):
        matched = _limited_names(item.matched, ", ") or "—"
        missing = _limited_names(item.missing, ", ") or "ничего"
        blocks.append(
            f"\n<b>{index}. {escape(item.dish.name)}</b> — совпало "
            f"{len(item.matched)}\n✅ {matched}\nДополнительно: {missing}"
        )
    return "\n".join(blocks)


def selected_text(names: list[str]) -> str:
    if not names:
        return "<b>Выбрано: 0</b>"
    visible = "\n".join(f"• {escape(name)} ×" for name in names[:PAGE_SIZE])
    if len(names) > PAGE_SIZE:
        visible += f"\n… ещё {len(names) - PAGE_SIZE}"
    return f"<b>Выбрано: {len(names)}</b>\n{visible}"
