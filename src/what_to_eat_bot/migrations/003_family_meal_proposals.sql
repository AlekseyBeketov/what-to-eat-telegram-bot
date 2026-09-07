CREATE TABLE family_meal_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    dish_id INTEGER REFERENCES dishes(id) ON DELETE SET NULL,
    proposer_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    dish_name TEXT NOT NULL,
    meal_type TEXT NOT NULL REFERENCES dish_types(code),
    ingredients_json TEXT NOT NULL,
    proposer_message_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK(status IN ('open', 'agreed', 'cancelled', 'expired')),
    expires_at TEXT NOT NULL,
    closed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_family_meal_proposals_family_created
    ON family_meal_proposals(family_id, created_at DESC);
CREATE UNIQUE INDEX ux_family_meal_proposals_open_dish
    ON family_meal_proposals(proposer_id, dish_id)
    WHERE status = 'open';

CREATE TABLE family_meal_proposal_recipients (
    proposal_id INTEGER NOT NULL REFERENCES family_meal_proposals(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    accepted INTEGER CHECK(accepted IN (0, 1)),
    responded_at TEXT,
    message_id INTEGER,
    PRIMARY KEY(proposal_id, user_id)
);
CREATE INDEX ix_family_meal_proposal_recipients_user
    ON family_meal_proposal_recipients(user_id, proposal_id);
