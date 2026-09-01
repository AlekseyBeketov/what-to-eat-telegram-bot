## Context

Новый single-process Telegram long-polling bot должен реализовать F1–F29 из `docs/Требования.md`, работать локально и под systemd без внешних сервисов.

## Goals / Non-Goals

**Goals:** async handlers, thin Telegram layer, тестируемые services/repositories, SQLite migrations, персональный/семейный ACL, deterministic ranking, safe configuration и graceful shutdown.

**Non-Goals:** inventory quantities, recipes, nutrition, shopping lists, web UI, Docker, microservices, embeddings/vector DB.

## Decisions

- Python 3.13 и aiogram 3.x: современный async stack; Python 3.12+ поддерживается.
- `aiosqlite` и versioned SQL migrations: минимальные dependencies и воспроизводимая схема; foreign keys включаются для каждого connection.
- `pydantic-settings`: typed environment configuration и fail-fast без раскрытия значений.
- FSM в memory storage: один polling process; незавершённый wizard можно безопасно начать заново после restart. Persisted domain state хранится в SQLite.
- Слои `handlers → services → repositories → SQLite`, composition root в `app.py`; hidden singletons отсутствуют.
- Canonical ingredients + aliases + Unicode normalization/prefix search достаточны; embeddings не добавляются. FTS5 не нужен при ожидаемом небольшом семейном каталоге.
- Ranking: обязательный ingredient фильтрует; затем coverage выбранных, доля совпадений по небазовым ingredients, favorite boost, recent penalty; tie-breakers — score, matched count, normalized title, id.
- Family visibility определяется author membership; mutate разрешён автору, а family members видят изменения и общий каталог. После выхода остаются только собственные dishes.
- Invite tokens генерируются через `secrets`, хранятся как SHA-256 hash, одноразовы и имеют expiry.

## Risks / Trade-offs

- [Memory FSM теряется при restart] → пользователь повторяет только незавершённый wizard; данные не теряются.
- [SQLite single-writer contention] → WAL, short transactions, indexes и один process.
- [Callback replay] → idempotent operations, ownership checks и state validation.
- [Нормализация не покрывает семантику NLP] → управляемые aliases; fuzzy/vector search отложены до измеримой необходимости.

## Migration Plan

При старте или отдельной CLI-командой применяются pending SQL migrations в transaction. Перед update на сервере создаётся SQLite backup; rollback выполняется возвратом к backup и предыдущей revision приложения.

## Open Questions

Нет блокирующих вопросов; продуктовые неоднозначности решаются в пользу минимального числа действий и безопасного доступа.
