## 1. Presentation Rules and Tests

- [x] 1.1 Add focused keyboard/formatter tests for standardized meal labels, row grouping, main-menu emoji, compact footers, and removed actions
- [x] 1.2 Add handler tests for five-item pages, visible concrete selections without pagination noise, consistent recommendation refresh, and list-input wording
- [x] 1.3 Add add/edit dish flow tests for confirmation row order, cancellation availability, comma parsing, and keyboard-free save confirmation

## 2. Shared UI Conventions

- [x] 2.1 Centralize meal labels and five-item page sizing, then replace old emoji/text across runtime code and the initial migration
- [x] 2.2 Update shared keyboard builders to enforce the requested row grouping, footer ordering, and removed shortcuts/actions
- [x] 2.3 Update every list prompt to mention Enter/new lines or commas and verify both delimiters remain accepted

## 3. Flow-Specific UX

- [x] 3.1 Render initial and refreshed “Что приготовить” results through the same text and keyboard builder
- [x] 3.2 Add visible selection separators to catalog/filter transitions while keeping pagination callbacks message-free
- [x] 3.3 Apply five-item pages and compact navigation/cancel footers across catalog, ingredients, settings, and recommendation collections
- [x] 3.4 Rework new-dish review actions and remove the keyboard after successful save

## 4. Verification

- [x] 4.1 Run focused handler/keyboard tests and fix regressions
- [x] 4.2 Run the full pytest suite, Ruff checks, OpenSpec validation, CodeGraph sync, and `git diff --check`
- [x] 4.3 Review the final diff for requirement coverage and unintended changes
