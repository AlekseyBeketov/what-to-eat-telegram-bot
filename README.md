# What to Eat Bot

Легковесный Telegram-бот, который подбирает блюда из личного или семейного каталога по продуктам пользователя. Основной сценарий: выбрать тип еды, ввести один или несколько равноправных продуктов по одному с новой строки, затем получить объяснимый ranked list с совпавшими и недостающими ингредиентами.

## Stack

- Python 3.12+ (локальная проверка выполняется на Python 3.13)
- aiogram 3.x, async long polling
- SQLite + aiosqlite + versioned SQL migrations
- pydantic-settings для typed environment configuration
- pytest/pytest-asyncio и Ruff

Внешняя БД, Redis, Docker и vector database не нужны.

## Структура

```text
src/what_to_eat_bot/
├── application/       # use cases, normalization, ranking
├── domain/            # entities and domain errors
├── handlers/          # aiogram routers, keyboards, FSM
├── migrations/        # ordered SQL migrations
├── repositories/      # SQLite access and ACL
├── app.py              # composition root and polling lifecycle
├── config.py           # typed env configuration
├── database.py         # connections and migration runner
└── __main__.py         # process entry point
tests/                  # temporary-SQLite and mocked-handler tests
docs/                   # specification, traceability and deployment
deploy/                 # systemd unit template
```

## Локальная установка после clone

Нужен Python 3.12 или новее.

```bash
cd /path/to/what-to-eat-bot
python3.13 -m venv .venv   # либо python3.12
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Альтернатива через `uv`:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt -e .
```

## Конфигурация

```bash
cp .env.example .env
chmod 600 .env
```

Заполните `BOT_TOKEN` в `.env`. Не добавляйте `.env` в Git. Доступные variables:

- `BOT_TOKEN` — обязательно;
- `DATABASE_PATH` — по умолчанию `./data/what_to_eat.sqlite3`;
- `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`;
- `INVITE_TTL_HOURS` — срок действия family invite;
- `BOT_USERNAME` — username без `@` для family deep links.

При отсутствии токена приложение завершается с названием неверной variable, не выводя значение.

## Migrations

```bash
source .venv/bin/activate
python -m what_to_eat_bot.migrate
```

Команда создаёт parent directory и применяет только pending migrations. Foreign keys включаются для каждого connection.

## Запуск

```bash
source .venv/bin/activate
python -m what_to_eat_bot
```

Остановка: `Ctrl+C`. aiogram обрабатывает `SIGINT`/`SIGTERM`, завершает polling и закрывает Telegram session/FSM storage.

Не запускайте два polling process с одним token: Telegram вернёт conflict для `getUpdates`.

## Tests и lint

Tests не используют реальный Telegram API или production database:

```bash
source .venv/bin/activate
pytest -q
ruff check .
ruff format --check .
```

Auto-format локально:

```bash
ruff format .
```

## Основные решения

- Canonical ingredients и aliases устраняют дубли; используются normalization, prefix/substring search и text parsing.
- При текстовом вводе бот предлагает указывать каждый ингредиент с новой строки. Старый ввод через запятую также поддерживается для совместимости.
- Поиск не зависит от регистра и считает `е`/`ё` эквивалентными.
- Ranking детерминирован: coverage выбранных продуктов, completeness блюда, небольшой favorite boost и bounded recent penalty. Блюда без совпадений исключаются.
- Basic ingredients не считаются недостающими и не ухудшают score.
- Family invites случайные, одноразовые и expiring; в SQLite хранится только SHA-256 hash.
- Участники семьи видят общий каталог, но изменять и удалять блюдо может только его автор.
- FSM хранится в memory: после restart незавершённый wizard начинается заново, persisted domain data остаётся в SQLite.

Подробности: [SPEC](docs/SPEC.md), [план](docs/PLAN.md) и [F1–F29 traceability](docs/REQUIREMENTS_TRACEABILITY.md).

## Deployment

Инструкция для Ubuntu/Debian и systemd: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Troubleshooting

### `Missing or invalid environment variable: BOT_TOKEN`

Проверьте наличие `.env`, имя `BOT_TOKEN` и запуск из корня repository. Значение token не должно быть пустым.

### `TelegramConflictError` / terminated by other getUpdates request

С тем же token уже работает другой polling process. Остановите только известный service/process; не используйте широкий `pkill python`.

### `unable to open database file` / `readonly database`

Проверьте parent directory `DATABASE_PATH` и write permissions пользователя процесса. Для systemd ожидается `/var/lib/what-to-eat-bot`.

### `database is locked`

Убедитесь, что запущен один bot process. Приложение использует WAL, busy timeout и короткие transactions, но не рассчитано на несколько writers.

### Family link показывает недействительное приглашение

Invite мог истечь или уже использоваться. Создайте новый через `⚙️ Настройки → Моя семья`.

### Логи

Локально JSON logs идут в stdout. Под systemd используйте:

```bash
journalctl -u what-to-eat-bot -n 200 --no-pager
```
