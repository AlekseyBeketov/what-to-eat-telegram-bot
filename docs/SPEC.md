# Спецификация What to Eat Bot

Источник истины по продуктовым требованиям: [`Требования.md`](./Требования.md).

## Цель

За несколько действий вернуть релевантные блюда из привычного личного или семейного рациона по выбранным продуктам и помочь выбрать одно блюдо.

## Первая рабочая версия

Включает обязательные F1–F22, F24, F28–F29 и практичную реализацию F23/F25. F26–F27 оставлены расширяемыми через таблицы тегов без обязательного UI. Поддерживаются onboarding, каталог/CRUD, canonical ingredients и aliases, подбор, персонализация, история и семьи.

## Основные сценарии

1. `/start` → onboarding пустого каталога → создание первого блюда.
2. Главное меню → добавление блюда → название → тип → ingredients кнопками/текстом → preview → save.
3. Каталог → type/search/page → card → favorite/edit/confirmed delete/cooked.
4. Подбор → type → основной ingredient → дополнительные → ranked results с matched/missing → card.
5. «Что приготовить?» → type → варианты → другие варианты без быстрых повторов → выбор.
6. Настройки → basic/favorite ingredients, usage stats и family.
7. Family → create/invite → explicit join → shared catalog → leave with personal dishes preserved.

## Сущности и инварианты

- `users`, `dish_types`, `dishes`, `ingredients`, `ingredient_aliases`, `dish_ingredients`.
- `favorite_dishes`, `basic_ingredients`, `favorite_ingredients`, `ingredient_usage`, `cooking_history`.
- `families`, `family_members`, `family_invites`; `dish_tags`/`dish_tag_links` — extension point.
- Dish всегда имеет author, type и хотя бы один ingredient.
- Canonical ingredient уникален по normalized name; alias уникален и ссылается на один canonical ingredient.
- Видимость dish: author либо current member той же family. Mutation dish — только author.
- После leave пользователь видит свои dishes и теряет доступ к чужим.
- Invite token: криптографически случайный, в БД только SHA-256 hash, expiry, one-time acceptance в transaction.
- Deletes подтверждаются; foreign keys включены на каждом connection; критичные изменения транзакционны.

## Ranking

До scoring применяются visibility/type filters. Все выбранные продукты равноправны; блюда без единого совпадения исключаются. Для каждого dish:

- `selected_non_basic` — выбранные ingredients без пользовательских basic;
- `matched` — пересечение dish ingredients с selected;
- `missing` — dish ingredients минус selected и basic;
- `coverage = len(matched) / max(1, len(selected_non_basic))`;
- `completeness = len(matched) / max(1, len(dish_non_basic))`;
- `score = 100*coverage + 25*completeness + 3*is_favorite - min(10, recent_penalty)`.

`recent_penalty` равен 10/6/3 для приготовления менее 1/3/7 дней назад, иначе 0. Tie-breakers: score desc, matched count desc, missing count asc, normalized title asc, id asc. Basic ingredients не считаются missing и не ухудшают score. Формула детерминирована и тестируется отдельно.

## Архитектурные решения

- Python 3.13 runtime (поддерживается 3.12+), aiogram 3.x, `aiosqlite`, `pydantic-settings`, pytest/pytest-asyncio, Ruff.
- Layering: `handlers → application services → repositories → SQLite`; domain models не зависят от Telegram.
- Composition root создаёт dependencies явно. FSM — MemoryStorage для незавершённых dialogs; persisted data — SQLite.
- Versioned SQL migrations с таблицей `schema_migrations`; WAL, busy timeout, indexes.
- Long polling через aiogram lifecycle с signal handling и закрытием session/storage/database.
- Prefix/substring search и managed aliases достаточны для небольшого каталога. FTS5/fuzzy можно добавить после измерения; embeddings/vector DB не оправданы.
- Callback payload короткий и валидируется по state/ownership; repeated actions idempotent.

## Нефункциональные требования

No secrets in tracked files/logs, один polling process, временные SQLite databases в tests, pagination, user-friendly expected errors, systemd service с явными filesystem protections и отдельным writable data directory; на текущем сервере используется запуск от root для совместимости с соседними services, backup-before-update instructions.

## Отложено

- F23 UI истории реализуется минимально; расширенная аналитика отложена.
- F25 использует bounded favorite/recency signals без ML.
- F26 schema extension point есть, обязательный tag UI отсутствует.
- F27 tag-based recommendation UI отложен как явно будущий.

## Out of scope

Количество/граммы/остатки/сроки годности, auto-write-off, shopping list, calories/diets, recipe generation/steps, costs, web admin, Docker/Kubernetes, external/vector databases и microservices.
