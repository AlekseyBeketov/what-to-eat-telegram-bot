## ADDED Requirements

### Requirement: Guided Telegram experience
The system SHALL provide onboarding, a compact main menu, button-first wizards, text alternatives, back/cancel actions, selected-item visibility, and expected-error messages.

#### Scenario: Empty catalog onboarding
- **WHEN** a new user sends `/start`
- **THEN** the bot explains the product and offers adding the first dish

### Requirement: Safe navigation
The system SHALL paginate long lists, keep callback data within Telegram limits, validate state and ownership, and handle repeated or stale callbacks idempotently.

#### Scenario: Replayed delete callback
- **WHEN** a confirmed delete callback is delivered twice
- **THEN** the second delivery produces a harmless stale-action response and no unrelated data changes

### Requirement: Core flow
The system SHALL support the path from `/start` through product/type selection to an explainable dish choice without requiring a live Telegram API in service tests.

#### Scenario: Choose dinner
- **WHEN** a user selects dinner, a main product, optional products, and requests results
- **THEN** the bot displays ranked family-visible dinner dishes and lets the user open a dish card
