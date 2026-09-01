## ADDED Requirements

### Requirement: Deterministic ingredient ranking
The system SHALL filter by meal type, exclude dishes with no selected ingredient matches, then deterministically rank visible dishes by coverage of equally weighted selected ingredients, missing non-basic ingredients, favorite preference, recency, title, and id.

#### Scenario: Partial matches
- **WHEN** selected ingredients partially match several dishes
- **THEN** results are stable, highest-overlap dishes appear first, and each result lists matched and missing non-basic ingredients

### Requirement: Basic ingredients
The system SHALL let users mark ingredients as always available so they neither reduce ranking nor appear as critical missing items.

#### Scenario: Always-available salt
- **WHEN** salt is marked basic and is absent from selected products
- **THEN** a dish requiring salt is not penalized and salt is omitted from missing items

### Requirement: Diverse suggestions
The system SHALL suggest dishes by type and avoid immediate repeats when enough alternatives exist, using favorite and cooking history only as bounded signals.

#### Scenario: More options
- **WHEN** a user requests another suggestion set and unseen alternatives exist
- **THEN** the next set excludes the immediately shown dishes
