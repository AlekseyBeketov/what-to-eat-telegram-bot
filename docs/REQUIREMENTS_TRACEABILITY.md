# Соответствие требованиям F1–F29

Источник: [`Требования.md`](./Требования.md). Статус обновляется только после фактической реализации и проверки.

| ID | Кратко | Этап | Статус | Проверка |
|---|---|---:|---|---|
| F1 | Добавление блюда | 2 | Реализовано | FSM integration + repository test |
| F2 | Ingredients кнопками/текстом | 2 | Реализовано | parser/unit + mocked handler test |
| F3 | Просмотр/изменение выбранных | 2 | Реализовано | keyboard/FSM state test |
| F4 | Каталог и категории | 3 | Реализовано | repository + handler pagination test |
| F5 | Карточка блюда | 3 | Реализовано | formatter/handler test |
| F6 | Редактирование | 3 | Реализовано | service ACL + FSM test |
| F7 | Подтверждаемое удаление | 3 | Реализовано | confirmation/replayed callback test |
| F8 | Favorite dishes | 3 | Реализовано | repository/service test |
| F9 | Подбор по продуктам | 4 | Реализовано | end-to-end service/handler test |
| F10 | Ranking | 4 | Реализовано | deterministic ranking unit tests |
| F11 | Matched/missing | 4 | Реализовано | recommendation explanation test |
| F12 | Основной ingredient | 4 | Заменено явным решением пользователя: все выбранные продукты равноправны | equal-ranking/no-match exclusion tests |
| F13 | Frequent/recent/favorite quick list | 5 | Реализовано | usage query/service test |
| F14 | Ingredient search | 2 | Реализовано | normalized prefix search test |
| F15 | Normalization/aliases | 2 | Реализовано | case/space/ё/alias tests |
| F16 | Basic products | 4–5 | Реализовано | ranking/missing settings tests |
| F17 | «Что приготовить?» | 5 | Реализовано | suggestion service/handler test |
| F18 | Другие варианты | 5 | Реализовано | no-immediate-repeat test |
| F19 | Meal type filter | 3–5 | Реализовано | catalog/ranking/suggestion tests |
| F20 | Dish search | 3 | Реализовано | normalized substring test |
| F21 | Быстрое создание ingredient | 2 | Реализовано | explicit confirmation FSM test |
| F22 | Settings | 5 | Реализовано | settings handler/service tests |
| F23 | Cooking history (optional UI) | 5 | Реализовано | persisted history/list test |
| F24 | «Приготовил» | 5 | Реализовано | history write/idempotency test |
| F25 | Smart random (future-oriented) | 5 | Реализовано | bounded favorite/recency test |
| F26 | Dish tags (optional first version) | 1 | Реализован extension point | schema migration test |
| F27 | Tag recommendations (future) | — | Отложено по ТЗ | documented extension point |
| F28 | Personal catalog isolation | 1–6 | Реализовано | cross-user access tests |
| F29 | Family shared catalog | 6 | Реализовано | invite/join/shared/leave/ACL tests |
