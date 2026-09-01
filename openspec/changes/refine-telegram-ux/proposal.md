## Why

The bot’s inline keyboards and list views are visually inconsistent: related choices are not grouped, some flows lack a clear cancel path, repeated recommendation blocks change shape, and long lists or full-width single-button rows make conversations hard to scan. The interaction model should be predictable across catalog, recommendation, ingredient-selection, and dish-editing flows.

## What Changes

- Standardize meal-type labels and emoji as `☕️ Завтрак`, `🍗 Обед/ужин`, and `🍽️ Все блюда`, with meal types sharing one row and cancel on a dedicated row.
- Change the main-menu label to `📚 Мои блюда`.
- Render recommendation refreshes with the same heading, item buttons, and footer actions as the initial recommendation result.
- Limit every visible collection page to five items.
- Add visible user-choice separators for concrete catalog/filter selections while keeping pagination callbacks silent.
- Ensure interactive input/selection screens expose cancel, with footer rows limited to two buttons and save/done placed left of cancel.
- Simplify wide single-button layouts where buttons can be paired without reducing clarity.
- Remove frequent/recent quick picks and the dish-card “use for selection” action from the add-dish/catalog experience.
- Teach newline or comma-separated list input everywhere a list is requested.
- Remove the keyboard from the final “dish saved” confirmation.

## Capabilities

### New Capabilities

- `telegram-ux-consistency`: Consistent Telegram labels, keyboard grouping, list pagination, selection separators, cancellation, and list-input prompts across bot flows.

### Modified Capabilities

_None. The existing build change is complete but not archived; this follow-up defines its UX delta as a dedicated capability._

## Impact

- Telegram handlers and shared keyboard/formatter helpers under `src/what_to_eat_bot/handlers/`.
- Handler/FSM tests and pagination assertions under `tests/`.
- User-visible labels stored in the initial migration and documentation/spec traceability where applicable.
- No database schema or external API changes.
