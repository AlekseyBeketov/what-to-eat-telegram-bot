from what_to_eat_bot.domain.models import MealType

PAGE_SIZE = 5
BREAKFAST_LABEL = "☕️ Завтрак"
MAIN_LABEL = "🍗 Обед/ужин"
ALL_DISHES_LABEL = "🍽️ Все блюда"
PREVIOUS_PAGE_LABEL = "⏪ Назад"
NEXT_PAGE_LABEL = "⏩ Вперед"
MEAL_TYPE_LABELS = {
    MealType.BREAKFAST: BREAKFAST_LABEL,
    MealType.MAIN: MAIN_LABEL,
}
MEAL_CHOICE_LABELS = {
    MealType.BREAKFAST.value: BREAKFAST_LABEL,
    MealType.MAIN.value: MAIN_LABEL,
    "any": ALL_DISHES_LABEL,
}
LIST_INPUT_HINT = "по одному на строке (Enter) или через запятую"
