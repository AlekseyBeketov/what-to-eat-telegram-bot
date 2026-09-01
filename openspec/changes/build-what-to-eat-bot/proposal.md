## Why

Пользователю нужен быстрый способ выбрать блюдо из собственного или семейного рациона по доступным продуктам без внешней инфраструктуры и сложного учёта запасов.

## What Changes

- Реализуется async Telegram-бот с long polling, SQLite и воспроизводимыми migrations.
- Добавляются персональный каталог блюд, canonical ingredients/aliases, поиск, CRUD и избранное.
- Добавляются детерминированный подбор по равноправным выбранным продуктам и объяснение результата.
- Добавляются персонализация, история приготовления и семейный каталог с безопасными одноразовыми приглашениями.
- Добавляются автоматические тесты, эксплуатационная документация и systemd unit template.

## Capabilities

### New Capabilities
- `meal-catalog`: Персональный и семейный каталог, ингредиенты, поиск, CRUD и избранное.
- `meal-recommendations`: Подбор по продуктам, ranking, базовые продукты и разнообразные случайные предложения.
- `telegram-experience`: Onboarding, меню, FSM-сценарии, пагинация и безопасные callbacks.
- `family-sharing`: Семьи, приглашения, совместный доступ и выход из семьи.
- `operations`: Configuration, SQLite migrations, logging, graceful shutdown, тестирование и systemd deployment.

### Modified Capabilities

Нет существующих capabilities.

## Impact

Новый Python application в `src/what_to_eat_bot`, SQLite schema/migrations, Telegram handlers, тесты, документация и Linux deployment template. Production dependencies ограничены aiogram, aiosqlite и pydantic-settings; Redis, внешняя БД и vector search не требуются.
