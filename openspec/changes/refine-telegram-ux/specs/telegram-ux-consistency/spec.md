## ADDED Requirements

### Requirement: Consistent meal and menu labels
The bot SHALL label meal choices as `☕️ Завтрак`, `🍗 Обед/ужин`, and `🍽️ Все блюда` everywhere they are presented, SHALL place breakfast and lunch/dinner on one keyboard row, SHALL place all dishes on the next row, and SHALL place cancel on the final row. The main reply menu SHALL label the catalog action as `📚 Мои блюда`.

#### Scenario: Meal-type selection layout
- **WHEN** the bot asks the user to choose a meal type with all-types support
- **THEN** breakfast and lunch/dinner appear together on row one, all dishes appears on row two, and cancel appears on row three

#### Scenario: Menu catalog label
- **WHEN** the bot renders the main reply keyboard
- **THEN** the catalog entry is shown as `📚 Мои блюда`

### Requirement: Consistent recommendation refresh
The bot SHALL render initial and refreshed cooking recommendations with the same heading, per-dish buttons, item limit, and footer actions.

#### Scenario: User requests other recommendations
- **WHEN** the user presses `Другие варианты` or `Ещё варианты`
- **THEN** the next result is headed `Сегодня можно приготовить:` and has the same keyboard structure as the initial result

### Requirement: Collection page size
The bot SHALL show at most five elements on every page of a collection, including dishes, ingredients, categories, search results, and recommendation results.

#### Scenario: Collection contains more than five elements
- **WHEN** a collection view contains six or more elements
- **THEN** no more than five elements are rendered and navigation is offered when another page exists

### Requirement: Visible concrete selections
The bot SHALL add a visible chat separator for concrete catalog or filter choices that transition to a new result set, and SHALL NOT add new separator messages for pagination-only navigation.

#### Scenario: User selects all dishes
- **WHEN** the user presses `Все блюда` from the catalog categories
- **THEN** the chat visibly records that choice before the dish result is presented

#### Scenario: User changes a list page
- **WHEN** the user uses previous or next pagination
- **THEN** the current result is updated without an additional choice separator message

### Requirement: Escapable interaction flows
Every screen that accepts user input or a mutable selection SHALL expose `❌ Отмена`. Footer rows SHALL contain at most two buttons; when completion/save and cancel coexist, completion/save SHALL be left and cancel SHALL be right. If back and cancel coexist, they SHALL share the lowest practical footer row.

#### Scenario: Completing a selection
- **WHEN** a selection screen can be completed or cancelled
- **THEN** its footer contains `Готово` or `Сохранить` on the left and `Отмена` on the right

#### Scenario: Returning from a nested selection
- **WHEN** a screen has both back and cancel actions
- **THEN** both actions are available in the footer with no more than two buttons on that row

### Requirement: Compact keyboard layout
The bot SHALL avoid unnecessary full-width single-button rows by pairing compatible actions while preserving a maximum of two buttons per row and no more than four footer rows.

#### Scenario: Multiple compatible footer actions
- **WHEN** two compatible footer actions are available
- **THEN** they are rendered on the same row rather than separate full-width rows

### Requirement: Simplified add-dish choices
The add-dish flow SHALL NOT offer frequent or recent ingredient shortcuts, and dish cards SHALL NOT offer an `Использовать для подбора` action.

#### Scenario: User selects ingredients for a new dish
- **WHEN** the ingredient-selection keyboard is rendered
- **THEN** it contains neither `Частые` nor `Недавние`

#### Scenario: User opens a dish card
- **WHEN** the dish detail keyboard is rendered
- **THEN** it does not contain `Использовать для подбора`

### Requirement: Explicit list delimiters
Every prompt that requests a list SHALL state that items can be separated by Enter/new lines or commas, and the parser SHALL accept both forms.

#### Scenario: User enters a comma-separated ingredient list
- **WHEN** the user submits multiple ingredients separated by commas
- **THEN** the bot parses them as separate ingredients

#### Scenario: Bot asks for a list
- **WHEN** a list-input prompt is displayed
- **THEN** the prompt explicitly mentions Enter/new lines and commas as separators

### Requirement: New-dish confirmation layout
The new-dish confirmation keyboard SHALL render rename on row one, change type plus change ingredients on row two, and save plus cancel on row three. After a successful save, the confirmation message SHALL have no inline keyboard.

#### Scenario: User reviews a new dish
- **WHEN** the add-dish flow reaches confirmation
- **THEN** the actions follow the required three-row layout with save left of cancel

#### Scenario: Dish is saved
- **WHEN** the service successfully creates the dish
- **THEN** the bot sends `Блюдо сохранено. Теперь оно участвует в подборе.` without buttons
