# Последовательный план реализации

> Код реализуется без Git-коммитов. После каждого этапа запускаются focused tests и обновляется этот статус.

| Этап | Зависит от | Проверяемый результат | Статус |
|---|---|---|---|
| 0. Discovery и решения | — | Изучены требования/референс; `.env` ignored и untracked; созданы OpenSpec, SPEC, PLAN, traceability | Выполнен |
| 1. Foundation | 0 | Package/config/logging/migrations/repositories/entry point, `/start`, test scaffold; clean DB создаётся | Выполнен |
| 2. Каталог и ingredients | 1 | Onboarding, add wizard, types, canonical ingredients/aliases, CRUD tests | Выполнен |
| 3. Просмотр и управление | 2 | Catalog/counts/cards/search/pages/edit/confirmed delete/favorites | Выполнен |
| 4. Основной подбор | 3 | Type/main/additional selection, deterministic ranking, matched/missing/basic products | Выполнен |
| 5. Персонализация | 4 | Frequent/recent/favorite ingredients, diverse suggestions, cooked/history/settings | Выполнен |
| 6. Семья | 5 | Secure invites, join/leave, shared visibility, author ACL and tests | Выполнен |
| 7. Hardening и эксплуатация | 6 | Full QA, CodeGraph, docs, systemd, controlled live smoke, no orphan process | Выполнен |

## Детализация этапов

### 0. Discovery

Проверить Git и secrets; изучить `docs/Требования.md` и read-only reference; подтвердить актуальный stack через Context7; зафиксировать scope, schema, ranking, test seams.

### 1. Foundation

Создать `src/what_to_eat_bot/{domain,application,repositories,handlers,migrations}`; typed config; database lifecycle; migration CLI; composition root; fixtures и первый mocked handler test.

### 2. Каталог и ingredients

TDD для normalization/parser/aliases/duplicates/CRUD, затем FSM создания с preview/edit/cancel и кнопочным/text input.

### 3. Управление

TDD для visibility/search/pagination/favorite/delete confirmation/edit, затем thin handlers и stale callback behavior.

### 4. Подбор

TDD ranking formula/filters/basic products/explanations; затем FSM основного сценария и result cards.

### 5. Персонализация

Usage counters, recent/favorite ingredients, bounded random diversification, cooked/history/settings и regression tests.

### 6. Семья

Transactional family operations, hashed expiring one-time tokens, explicit confirmation, shared reads/author-only writes/leave semantics и isolation tests.

### 7. Delivery

Global errors, graceful shutdown, README/DEPLOYMENT/systemd, fresh venv install, full pytest/Ruff/migrations/imports/diff/secrets checks, controlled polling smoke and process cleanup.
