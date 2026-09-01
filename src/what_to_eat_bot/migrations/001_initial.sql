CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    username TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dish_types (
    code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL UNIQUE
);
INSERT INTO dish_types(code, display_name, sort_order) VALUES
    ('breakfast', '☕️ Завтрак', 10),
    ('main', '🍗 Обед/ужин', 20);

CREATE TABLE ingredient_categories (
    code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL UNIQUE
);
INSERT INTO ingredient_categories(code, display_name, sort_order) VALUES
    ('meat', '🥩 Мясо и птица', 10), ('fish', '🐟 Рыба и морепродукты', 20),
    ('vegetables', '🥕 Овощи', 30), ('fruit', '🍎 Фрукты', 40),
    ('grains', '🍚 Крупы', 50), ('pasta', '🍝 Макароны', 60),
    ('dairy', '🥛 Молочные продукты', 70), ('cheese', '🧀 Сыры', 80),
    ('eggs', '🥚 Яйца', 90), ('bakery', '🍞 Хлеб и выпечка', 100),
    ('legumes', '🫘 Бобовые', 110), ('greens', '🌿 Зелень', 120),
    ('seasoning', '🧂 Соусы и приправы', 130), ('other', '📦 Другое', 140);

CREATE TABLE ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    category_code TEXT NOT NULL DEFAULT 'other' REFERENCES ingredient_categories(code),
    created_by INTEGER REFERENCES users(telegram_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_ingredients_category_name ON ingredients(category_code, normalized_name);

CREATE TABLE ingredient_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL UNIQUE
);
CREATE INDEX ix_aliases_ingredient ON ingredient_aliases(ingredient_id);

CREATE TABLE dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    meal_type TEXT NOT NULL REFERENCES dish_types(code),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(author_id, normalized_name)
);
CREATE INDEX ix_dishes_author_type_name ON dishes(author_id, meal_type, normalized_name);

CREATE TABLE dish_ingredients (
    dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    PRIMARY KEY(dish_id, ingredient_id)
);
CREATE INDEX ix_dish_ingredients_ingredient ON dish_ingredients(ingredient_id, dish_id);

CREATE TABLE favorite_dishes (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, dish_id)
);

CREATE TABLE basic_ingredients (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    PRIMARY KEY(user_id, ingredient_id)
);

CREATE TABLE favorite_ingredients (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    PRIMARY KEY(user_id, ingredient_id)
);

CREATE TABLE ingredient_usage (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    use_count INTEGER NOT NULL DEFAULT 0 CHECK(use_count >= 0),
    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, ingredient_id)
);
CREATE INDEX ix_usage_user_recent ON ingredient_usage(user_id, last_used_at DESC);

CREATE TABLE cooking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    cooked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_history_user_recent ON cooking_history(user_id, cooked_at DESC);
CREATE INDEX ix_history_dish_recent ON cooking_history(dish_id, cooked_at DESC);

CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    suggestion_count INTEGER NOT NULL DEFAULT 3 CHECK(suggestion_count BETWEEN 1 AND 10),
    avoid_recent_days INTEGER NOT NULL DEFAULT 7 CHECK(avoid_recent_days BETWEEN 0 AND 90)
);

CREATE TABLE families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE family_members (
    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(telegram_id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(family_id, user_id)
);
CREATE INDEX ix_family_members_family ON family_members(family_id, user_id);

CREATE TABLE family_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    accepted_by INTEGER REFERENCES users(telegram_id) ON DELETE SET NULL,
    accepted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK((accepted_by IS NULL AND accepted_at IS NULL) OR
          (accepted_by IS NOT NULL AND accepted_at IS NOT NULL))
);
CREATE INDEX ix_family_invites_family_expiry ON family_invites(family_id, expires_at);

CREATE TABLE dish_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);
CREATE TABLE dish_tag_links (
    dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES dish_tags(id) ON DELETE CASCADE,
    PRIMARY KEY(dish_id, tag_id)
);

INSERT INTO ingredients(name, normalized_name, category_code) VALUES
    ('Курица', 'курица', 'meat'), ('Говядина', 'говядина', 'meat'),
    ('Свинина', 'свинина', 'meat'), ('Рыба', 'рыба', 'fish'),
    ('Картофель', 'картофель', 'vegetables'), ('Лук', 'лук', 'vegetables'),
    ('Морковь', 'морковь', 'vegetables'), ('Помидоры', 'помидоры', 'vegetables'),
    ('Огурцы', 'огурцы', 'vegetables'), ('Перец болгарский', 'перец болгарский', 'vegetables'),
    ('Кабачок', 'кабачок', 'vegetables'), ('Баклажан', 'баклажан', 'vegetables'),
    ('Чеснок', 'чеснок', 'vegetables'), ('Рис', 'рис', 'grains'),
    ('Гречка', 'гречка', 'grains'), ('Овсянка', 'овсянка', 'grains'),
    ('Макароны', 'макароны', 'pasta'), ('Молоко', 'молоко', 'dairy'),
    ('Сливки', 'сливки', 'dairy'), ('Сыр', 'сыр', 'cheese'),
    ('Яйца', 'яйца', 'eggs'), ('Хлеб', 'хлеб', 'bakery'),
    ('Фасоль', 'фасоль', 'legumes'), ('Зелень', 'зелень', 'greens'),
    ('Соль', 'соль', 'seasoning'), ('Черный перец', 'черный перец', 'seasoning'),
    ('Растительное масло', 'растительное масло', 'seasoning'), ('Вода', 'вода', 'other'),
    ('Сахар', 'сахар', 'seasoning');

INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Картошка', 'картошка' FROM ingredients WHERE normalized_name = 'картофель';
INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Куриная грудка', 'куриная грудка' FROM ingredients WHERE normalized_name = 'курица';
INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Грудка', 'грудка' FROM ingredients WHERE normalized_name = 'курица';
INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Филе курицы', 'филе курицы' FROM ingredients WHERE normalized_name = 'курица';
INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Масло', 'масло' FROM ingredients WHERE normalized_name = 'растительное масло';
INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
SELECT id, 'Перец', 'перец' FROM ingredients WHERE normalized_name = 'черный перец';
