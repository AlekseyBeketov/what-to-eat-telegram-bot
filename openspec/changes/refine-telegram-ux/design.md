## Context

The aiogram bot builds keyboards directly in several handlers plus shared helpers in `handlers/keyboards.py`. This has allowed labels, footer placement, pagination size, and recommendation rendering to diverge between otherwise related flows. Telegram renders an inline keyboard row at the width of the message/keyboard container, so unnecessary one-button rows make compact prompts look disproportionately wide.

## Goals / Non-Goals

**Goals:**

- Establish one set of user-visible meal labels, menu emoji, list page size, list-input wording, and footer conventions.
- Keep initial and refreshed recommendation cards structurally identical.
- Make concrete filter choices visible in chat without producing noise during pagination.
- Keep all mutable/input FSM states escapable through `❌ Отмена`.
- Cover the conventions with handler/keyboard tests that do not require Telegram API access.

**Non-Goals:**

- Redesign ranking, persistence, ownership, or family sharing.
- Change Telegram reply keyboards into inline keyboards or add new dependencies.
- Edit previously sent messages or migrate existing dish/category data beyond labels used by fresh databases.

## Decisions

1. **Centralize presentation constants and reusable keyboard rows.** Shared meal labels and the page-size constant will live in handler presentation code and be reused by keyboards/formatters/handlers. This avoids future text drift while keeping domain enum values unchanged. Duplicating literals in each handler was rejected because the current inconsistency came from that approach.

2. **Use five items per page for every collection surface.** Catalog dishes, recommendation candidates, ingredients, categories, quick results, and settings lists will cap visible item buttons/items at five before navigation. Five is small enough for mobile scanning and matches the requested product rule.

3. **Treat concrete filter selection differently from navigation.** For category/filter callbacks such as “Все блюда”, the bot will emit or preserve a short selection marker before the result. Pagination callbacks will continue editing/replacing the current result without adding chat messages. This gives visual separation without chat spam.

4. **Build recommendation result text and keyboard through one renderer.** Both initial suggestions and `suggest:more` will use `Сегодня можно приготовить:` and the same per-dish rows plus refresh/favorite footer. A refreshed page is a new sample of the same result type, not a separate information category.

5. **Standardize footer ordering.** Action rows contain at most two buttons. If completion and cancellation coexist, completion/save is left and cancel is right. Back/navigation and cancel share a footer row when both exist. The confirmation screen for a new dish uses three rows: rename; type + ingredients; save + cancel.

6. **Accept newline and comma delimiters in list parsing prompts.** Existing parsing remains backward-compatible; prompts explicitly teach both separators. Semicolon compatibility, if already supported, remains an implementation detail.

7. **Remove obsolete shortcuts rather than hide them.** Frequent/recent quick picks in add-dish and “use for selection” on dish cards are removed from keyboard construction and tests, reducing width and choice overload.

## Risks / Trade-offs

- **[Selection marker creates extra messages]** → Add it only for concrete category/filter transitions; pagination edits remain silent.
- **[Shared label changes miss stored seed labels]** → Update the initial migration label values as well as runtime formatters/keyboards and search the repository for old variants.
- **[Five-item cap changes existing pagination assumptions]** → Add focused boundary tests for exactly five, six, and subsequent pages.
- **[Telegram widths cannot be set directly]** → Reduce width indirectly by pairing compatible footer buttons and removing unnecessary one-button rows; accept that long text still determines minimum width.
