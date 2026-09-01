## ADDED Requirements

### Requirement: Personal meal catalog
The system SHALL let a user create, view, search, edit, favorite, and confirmation-delete dishes with a type and canonical ingredient set.

#### Scenario: Dish lifecycle
- **WHEN** a user completes the dish wizard and later edits or deletes the dish
- **THEN** the catalog and recommendations immediately reflect the confirmed change

### Requirement: Ingredient normalization
The system SHALL normalize case, spaces, `ё/е`, aliases, and comma-separated input while preventing duplicate canonical ingredients.

#### Scenario: Alias resolution
- **WHEN** a user enters multiple known aliases and new ingredient names
- **THEN** known aliases resolve to canonical ingredients and new names require explicit creation confirmation

### Requirement: Catalog access control
The system SHALL expose personal dishes only to their author or current family members and SHALL restrict mutation to the dish author.

#### Scenario: Unrelated user access
- **WHEN** an unrelated user queries or mutates another user's dish
- **THEN** the dish is absent or access is denied without leaking its data
