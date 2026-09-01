## 1. Discovery and specification

- [x] 1.1 Read product requirements, repository instructions, reference structure, runtime and deployment docs
- [x] 1.2 Verify Git state and protect the untracked `.env`
- [x] 1.3 Confirm Python/aiogram stack against current documentation
- [x] 1.4 Record architecture, scope, ranking and access-control decisions

## 2. Foundation

- [x] 2.1 Add package structure, pinned dependencies, typed config and logging
- [x] 2.2 Implement SQLite connection management and versioned migrations
- [x] 2.3 Implement domain models and repositories with ownership/family visibility
- [x] 2.4 Add composition root, polling entry point, `/start`, menus and test fixtures

## 3. Catalog and ingredients

- [x] 3.1 Implement normalization, aliases, text parsing, categories and ingredient search
- [x] 3.2 Implement dish CRUD, duplicate prevention and transaction boundaries
- [x] 3.3 Implement add/edit FSM with button and text ingredient selection
- [x] 3.4 Test onboarding, CRUD, normalization, aliases and mocked handler flows

## 4. Catalog management

- [x] 4.1 Implement category counts, paginated lists, cards and dish search
- [x] 4.2 Implement author-only editing, confirmation deletion and favorites
- [x] 4.3 Test pagination, stale callbacks, search, edit/delete and favorites

## 5. Recommendations and personalization

- [x] 5.1 Implement deterministic ranking for equal selected products, type filter and explanations
- [x] 5.2 Implement basic, frequent, recent and favorite ingredients
- [x] 5.3 Implement diverse “What to cook?”, cooked history and settings flows
- [x] 5.4 Test full/partial ranking, edge cases, repeat avoidance and history

## 6. Family sharing

- [x] 6.1 Implement family membership and secure hashed expiring single-use invites
- [x] 6.2 Implement join confirmation, shared visibility, author attribution and leave flow
- [x] 6.3 Test isolation, shared access, invalid/expired/reused invites and leaving

## 7. Hardening and delivery

- [x] 7.1 Add expected/global error handling, idempotency and graceful shutdown
- [x] 7.2 Complete README, deployment guide, env example and systemd unit template
- [x] 7.3 Initialize CodeGraph and run full tests, Ruff, migrations, imports and Git safety checks
- [x] 7.4 Run and stop a controlled live polling smoke test without exposing secrets
- [x] 7.5 Update traceability and final status from verified command output
