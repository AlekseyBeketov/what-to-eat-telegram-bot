from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from what_to_eat_bot.database import Database
from what_to_eat_bot.domain.errors import (
    AccessDeniedError,
    ConflictError,
    InvalidInviteError,
    NotFoundError,
)
from what_to_eat_bot.domain.models import Dish, FamilyInvite, Ingredient, MealType

_VISIBLE = """
(
    d.author_id = ? OR d.author_id IN (
        SELECT fm2.user_id
        FROM family_members fm1
        JOIN family_members fm2 ON fm2.family_id = fm1.family_id
        WHERE fm1.user_id = ?
    )
)
"""


class AppRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def ensure_user(
        self, telegram_id: int, display_name: str, username: str | None = None
    ) -> None:
        async with self.database.connect() as db:
            await db.execute(
                """
                INSERT INTO users(telegram_id, display_name, username)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    username = excluded.username,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, display_name, username),
            )
            await db.execute(
                "INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (telegram_id,)
            )
            await db.commit()

    async def get_user_name(self, user_id: int) -> str:
        async with self.database.connect() as db:
            row = await (
                await db.execute("SELECT display_name FROM users WHERE telegram_id = ?", (user_id,))
            ).fetchone()
            if row is None:
                raise NotFoundError("Пользователь не найден")
            return str(row[0])

    async def list_categories(self) -> list[tuple[str, str]]:
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    "SELECT code, display_name FROM ingredient_categories ORDER BY sort_order"
                )
            ).fetchall()
            return [(str(row[0]), str(row[1])) for row in rows]

    async def list_ingredients(
        self, category: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ingredient]:
        sql = "SELECT id, name, normalized_name, category_code FROM ingredients"
        params: list[Any] = []
        if category:
            sql += " WHERE category_code = ?"
            params.append(category)
        sql += " ORDER BY normalized_name LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.database.connect() as db:
            rows = await (await db.execute(sql, params)).fetchall()
            return [self._ingredient(row) for row in rows]

    async def get_ingredients(self, ingredient_ids: Iterable[int]) -> list[Ingredient]:
        ids = sorted(set(ingredient_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    f"""SELECT id, name, normalized_name, category_code FROM ingredients
                WHERE id IN ({placeholders}) ORDER BY normalized_name""",
                    ids,
                )
            ).fetchall()
            return [self._ingredient(row) for row in rows]

    async def resolve_ingredient(self, normalized_name: str) -> Ingredient | None:
        async with self.database.connect() as db:
            row = await (
                await db.execute(
                    """
                SELECT i.id, i.name, i.normalized_name, i.category_code
                FROM ingredients i
                LEFT JOIN ingredient_aliases a ON a.ingredient_id = i.id
                WHERE i.normalized_name = ? OR a.normalized_alias = ?
                LIMIT 1
                """,
                    (normalized_name, normalized_name),
                )
            ).fetchone()
            return self._ingredient(row) if row else None

    async def search_ingredients(self, normalized_query: str, limit: int = 10) -> list[Ingredient]:
        pattern = f"{self._escape_like(normalized_query)}%"
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    """
                SELECT DISTINCT i.id, i.name, i.normalized_name, i.category_code
                FROM ingredients i
                LEFT JOIN ingredient_aliases a ON a.ingredient_id = i.id
                WHERE i.normalized_name LIKE ? ESCAPE '\\'
                   OR a.normalized_alias LIKE ? ESCAPE '\\'
                ORDER BY i.normalized_name LIMIT ?
                """,
                    (pattern, pattern, limit),
                )
            ).fetchall()
            return [self._ingredient(row) for row in rows]

    async def create_ingredient(
        self, name: str, normalized_name: str, user_id: int, category: str = "other"
    ) -> Ingredient:
        async with self.database.connect() as db:
            try:
                cursor = await db.execute(
                    """INSERT INTO ingredients(name, normalized_name, category_code, created_by)
                    VALUES (?, ?, ?, ?)""",
                    (name, normalized_name, category, user_id),
                )
                await db.commit()
            except aiosqlite.IntegrityError as error:
                raise ConflictError("Такой ингредиент уже существует") from error
            return Ingredient(int(cursor.lastrowid), name, normalized_name, category)

    async def add_alias(self, ingredient_id: int, alias: str, normalized_alias: str) -> None:
        async with self.database.connect() as db:
            try:
                await db.execute(
                    """INSERT INTO ingredient_aliases(ingredient_id, alias, normalized_alias)
                    VALUES (?, ?, ?)""",
                    (ingredient_id, alias, normalized_alias),
                )
                await db.commit()
            except aiosqlite.IntegrityError as error:
                raise ConflictError("Такой alias уже используется") from error

    async def create_dish(
        self,
        author_id: int,
        name: str,
        normalized_name: str,
        meal_type: MealType,
        ingredient_ids: Sequence[int],
    ) -> int:
        unique_ids = sorted(set(ingredient_ids))
        if not unique_ids:
            raise ConflictError("Добавьте хотя бы один ингредиент")
        async with self.database.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """INSERT INTO dishes(author_id, name, normalized_name, meal_type)
                    VALUES (?, ?, ?, ?)""",
                    (author_id, name, normalized_name, meal_type.value),
                )
                dish_id = int(cursor.lastrowid)
                await db.executemany(
                    "INSERT INTO dish_ingredients(dish_id, ingredient_id) VALUES (?, ?)",
                    [(dish_id, ingredient_id) for ingredient_id in unique_ids],
                )
                await db.commit()
                return dish_id
            except aiosqlite.IntegrityError as error:
                await db.rollback()
                raise ConflictError(
                    "Блюдо с таким названием уже есть или данные неверны"
                ) from error

    async def update_dish(
        self,
        user_id: int,
        dish_id: int,
        name: str,
        normalized_name: str,
        meal_type: MealType,
        ingredient_ids: Sequence[int],
    ) -> None:
        unique_ids = sorted(set(ingredient_ids))
        if not unique_ids:
            raise ConflictError("Добавьте хотя бы один ингредиент")
        async with self.database.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """UPDATE dishes SET name=?, normalized_name=?, meal_type=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=? AND author_id=?""",
                    (name, normalized_name, meal_type.value, dish_id, user_id),
                )
                if cursor.rowcount != 1:
                    raise AccessDeniedError("Редактировать блюдо может только автор")
                await db.execute("DELETE FROM dish_ingredients WHERE dish_id=?", (dish_id,))
                await db.executemany(
                    "INSERT INTO dish_ingredients(dish_id, ingredient_id) VALUES (?, ?)",
                    [(dish_id, ingredient_id) for ingredient_id in unique_ids],
                )
                await db.commit()
            except (aiosqlite.IntegrityError, AccessDeniedError) as error:
                await db.rollback()
                if isinstance(error, AccessDeniedError):
                    raise
                raise ConflictError("Блюдо с таким названием уже существует") from error

    async def delete_dish(self, user_id: int, dish_id: int) -> bool:
        async with self.database.connect() as db:
            cursor = await db.execute(
                "DELETE FROM dishes WHERE id = ? AND author_id = ?", (dish_id, user_id)
            )
            await db.commit()
            return cursor.rowcount == 1

    async def get_dish(self, user_id: int, dish_id: int) -> Dish:
        async with self.database.connect() as db:
            rows = await self._fetch_dishes(
                db,
                user_id,
                "d.id = ?",
                [dish_id],
                limit=1,
                offset=0,
            )
            if not rows:
                raise NotFoundError("Блюдо не найдено или больше недоступно")
            return rows[0]

    async def list_dishes(
        self,
        user_id: int,
        meal_type: MealType | None = None,
        favorites_only: bool = False,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Dish]:
        conditions: list[str] = []
        params: list[Any] = []
        if meal_type:
            conditions.append("d.meal_type = ?")
            params.append(meal_type.value)
        if favorites_only:
            conditions.append("fd.user_id IS NOT NULL")
        if query:
            conditions.append("d.normalized_name LIKE ? ESCAPE '\\'")
            params.append(f"%{self._escape_like(query)}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        async with self.database.connect() as db:
            return await self._fetch_dishes(db, user_id, where, params, limit, offset)

    async def count_dishes(self, user_id: int, meal_type: MealType | None = None) -> int:
        params: list[Any] = [user_id, user_id]
        type_filter = ""
        if meal_type:
            type_filter = " AND d.meal_type = ?"
            params.append(meal_type.value)
        async with self.database.connect() as db:
            row = await (
                await db.execute(
                    f"SELECT COUNT(*) FROM dishes d WHERE {_VISIBLE}{type_filter}", params
                )
            ).fetchone()
            return int(row[0])

    async def toggle_favorite_dish(self, user_id: int, dish_id: int) -> bool:
        await self.get_dish(user_id, dish_id)
        async with self.database.connect() as db:
            existing = await (
                await db.execute(
                    "SELECT 1 FROM favorite_dishes WHERE user_id=? AND dish_id=?",
                    (user_id, dish_id),
                )
            ).fetchone()
            if existing:
                await db.execute(
                    "DELETE FROM favorite_dishes WHERE user_id=? AND dish_id=?",
                    (user_id, dish_id),
                )
                favorite = False
            else:
                await db.execute(
                    "INSERT INTO favorite_dishes(user_id, dish_id) VALUES (?, ?)",
                    (user_id, dish_id),
                )
                favorite = True
            await db.commit()
            return favorite

    async def set_basic_ingredient(self, user_id: int, ingredient_id: int, enabled: bool) -> None:
        await self._set_user_ingredient("basic_ingredients", user_id, ingredient_id, enabled)

    async def set_favorite_ingredient(
        self, user_id: int, ingredient_id: int, enabled: bool
    ) -> None:
        await self._set_user_ingredient("favorite_ingredients", user_id, ingredient_id, enabled)

    async def get_basic_ingredient_ids(self, user_id: int) -> set[int]:
        return await self._get_user_ingredient_ids("basic_ingredients", user_id)

    async def get_favorite_ingredient_ids(self, user_id: int) -> set[int]:
        return await self._get_user_ingredient_ids("favorite_ingredients", user_id)

    async def quick_ingredients(
        self, user_id: int, kind: str, limit: int = 12, offset: int = 0
    ) -> list[Ingredient]:
        if kind == "favorite":
            join = "JOIN favorite_ingredients x ON x.ingredient_id=i.id AND x.user_id=?"
            order = "i.normalized_name"
        elif kind == "recent":
            join = "JOIN ingredient_usage x ON x.ingredient_id=i.id AND x.user_id=?"
            order = "x.last_used_at DESC"
        else:
            join = "JOIN ingredient_usage x ON x.ingredient_id=i.id AND x.user_id=?"
            order = "x.use_count DESC, x.last_used_at DESC"
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    f"""SELECT i.id, i.name, i.normalized_name, i.category_code
                FROM ingredients i {join} ORDER BY {order} LIMIT ? OFFSET ?""",
                    (user_id, limit, offset),
                )
            ).fetchall()
            return [self._ingredient(row) for row in rows]

    async def record_ingredient_usage(self, user_id: int, ingredient_ids: Iterable[int]) -> None:
        unique_ids = set(ingredient_ids)
        async with self.database.connect() as db:
            await db.executemany(
                """INSERT INTO ingredient_usage(user_id, ingredient_id, use_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, ingredient_id) DO UPDATE SET
                    use_count=use_count+1, last_used_at=CURRENT_TIMESTAMP""",
                [(user_id, ingredient_id) for ingredient_id in unique_ids],
            )
            await db.commit()

    async def clear_ingredient_usage(self, user_id: int) -> None:
        async with self.database.connect() as db:
            await db.execute("DELETE FROM ingredient_usage WHERE user_id=?", (user_id,))
            await db.commit()

    async def mark_cooked(self, user_id: int, dish_id: int) -> None:
        dish = await self.get_dish(user_id, dish_id)
        async with self.database.connect() as db:
            await db.execute(
                "INSERT INTO cooking_history(user_id, dish_id) VALUES (?, ?)",
                (user_id, dish_id),
            )
            await db.executemany(
                """INSERT INTO ingredient_usage(user_id, ingredient_id, use_count)
                VALUES (?, ?, 1) ON CONFLICT(user_id, ingredient_id) DO UPDATE SET
                use_count=use_count+1, last_used_at=CURRENT_TIMESTAMP""",
                [(user_id, ingredient.id) for ingredient in dish.ingredients],
            )
            await db.commit()

    async def recent_cooked(self, user_id: int, limit: int = 10) -> list[tuple[Dish, datetime]]:
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    f"""SELECT h.dish_id, MAX(h.cooked_at) cooked_at
                FROM cooking_history h JOIN dishes d ON d.id=h.dish_id
                WHERE h.user_id=? AND {_VISIBLE}
                GROUP BY h.dish_id ORDER BY cooked_at DESC LIMIT ?""",
                    (user_id, user_id, user_id, limit),
                )
            ).fetchall()
        result: list[tuple[Dish, datetime]] = []
        for row in rows:
            result.append((await self.get_dish(user_id, int(row[0])), self._datetime(str(row[1]))))
        return result

    async def last_cooked_by_dish(self, user_id: int) -> dict[int, datetime]:
        async with self.database.connect() as db:
            rows = await (
                await db.execute(
                    """SELECT dish_id, MAX(cooked_at) FROM cooking_history
                WHERE user_id=? GROUP BY dish_id""",
                    (user_id,),
                )
            ).fetchall()
            return {int(row[0]): self._datetime(str(row[1])) for row in rows}

    async def get_settings(self, user_id: int) -> tuple[int, int]:
        async with self.database.connect() as db:
            row = await (
                await db.execute(
                    """SELECT suggestion_count, avoid_recent_days FROM user_settings
                WHERE user_id=?""",
                    (user_id,),
                )
            ).fetchone()
            return (int(row[0]), int(row[1])) if row else (3, 7)

    async def create_family(self, user_id: int, name: str) -> int:
        async with self.database.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                existing = await (
                    await db.execute(
                        "SELECT family_id FROM family_members WHERE user_id=?", (user_id,)
                    )
                ).fetchone()
                if existing:
                    raise ConflictError("Вы уже состоите в семье")
                cursor = await db.execute(
                    "INSERT INTO families(name, created_by) VALUES (?, ?)", (name, user_id)
                )
                family_id = int(cursor.lastrowid)
                await db.execute(
                    "INSERT INTO family_members(family_id, user_id) VALUES (?, ?)",
                    (family_id, user_id),
                )
                await db.commit()
                return family_id
            except Exception:
                await db.rollback()
                raise

    async def family_info(self, user_id: int) -> tuple[int, str, list[tuple[int, str]]] | None:
        async with self.database.connect() as db:
            family = await (
                await db.execute(
                    """SELECT f.id, f.name FROM families f JOIN family_members fm
                ON fm.family_id=f.id WHERE fm.user_id=?""",
                    (user_id,),
                )
            ).fetchone()
            if not family:
                return None
            members = await (
                await db.execute(
                    """SELECT u.telegram_id, u.display_name FROM users u JOIN family_members fm
                ON fm.user_id=u.telegram_id WHERE fm.family_id=? ORDER BY fm.joined_at""",
                    (family[0],),
                )
            ).fetchall()
            return int(family[0]), str(family[1]), [(int(r[0]), str(r[1])) for r in members]

    async def create_invite(self, user_id: int, token_hash: str, expires_at: datetime) -> int:
        info = await self.family_info(user_id)
        if not info:
            raise ConflictError("Сначала создайте семью")
        async with self.database.connect() as db:
            cursor = await db.execute(
                """INSERT INTO family_invites(family_id, created_by, token_hash, expires_at)
                VALUES (?, ?, ?, ?)""",
                (info[0], user_id, token_hash, expires_at.astimezone(UTC).isoformat()),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def inspect_invite(self, token_hash: str, now: datetime) -> FamilyInvite:
        async with self.database.connect() as db:
            row = await (
                await db.execute(
                    """SELECT i.family_id, f.name, u.display_name, i.expires_at,
                          i.accepted_at
                FROM family_invites i JOIN families f ON f.id=i.family_id
                JOIN users u ON u.telegram_id=i.created_by WHERE i.token_hash=?""",
                    (token_hash,),
                )
            ).fetchone()
            if not row or row[4] is not None or self._datetime(str(row[3])) <= now:
                raise InvalidInviteError(
                    "Приглашение недействительно, истекло или уже использовано"
                )
            return FamilyInvite(int(row[0]), str(row[1]), str(row[2]), self._datetime(str(row[3])))

    async def accept_invite(self, user_id: int, token_hash: str, now: datetime) -> int:
        async with self.database.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                row = await (
                    await db.execute(
                        """SELECT id, family_id, expires_at, accepted_at FROM family_invites
                    WHERE token_hash=?""",
                        (token_hash,),
                    )
                ).fetchone()
                if not row or row[3] is not None or self._datetime(str(row[2])) <= now:
                    raise InvalidInviteError(
                        "Приглашение недействительно, истекло или уже использовано"
                    )
                existing = await (
                    await db.execute(
                        "SELECT family_id FROM family_members WHERE user_id=?", (user_id,)
                    )
                ).fetchone()
                if existing:
                    raise ConflictError("Сначала выйдите из текущей семьи")
                await db.execute(
                    "INSERT INTO family_members(family_id, user_id) VALUES (?, ?)",
                    (row[1], user_id),
                )
                cursor = await db.execute(
                    """UPDATE family_invites SET accepted_by=?, accepted_at=?
                    WHERE id=? AND accepted_at IS NULL""",
                    (user_id, now.astimezone(UTC).isoformat(), row[0]),
                )
                if cursor.rowcount != 1:
                    raise InvalidInviteError("Приглашение уже использовано")
                await db.commit()
                return int(row[1])
            except Exception:
                await db.rollback()
                raise

    async def leave_family(self, user_id: int) -> bool:
        async with self.database.connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute("SELECT family_id FROM family_members WHERE user_id=?", (user_id,))
            ).fetchone()
            if not row:
                await db.rollback()
                return False
            family_id = int(row[0])
            await db.execute("DELETE FROM family_members WHERE user_id=?", (user_id,))
            count = await (
                await db.execute(
                    "SELECT COUNT(*) FROM family_members WHERE family_id=?", (family_id,)
                )
            ).fetchone()
            if int(count[0]) == 0:
                await db.execute("DELETE FROM families WHERE id=?", (family_id,))
            await db.commit()
            return True

    async def _fetch_dishes(
        self,
        db: aiosqlite.Connection,
        user_id: int,
        condition: str,
        condition_params: Sequence[Any],
        limit: int,
        offset: int,
    ) -> list[Dish]:
        rows = await (
            await db.execute(
                f"""
            SELECT d.id, d.author_id, u.display_name, d.name, d.normalized_name,
                   d.meal_type, CASE WHEN fd.user_id IS NULL THEN 0 ELSE 1 END favorite
            FROM dishes d JOIN users u ON u.telegram_id=d.author_id
            LEFT JOIN favorite_dishes fd ON fd.dish_id=d.id AND fd.user_id=?
            WHERE {_VISIBLE} AND ({condition})
            ORDER BY d.normalized_name, d.id LIMIT ? OFFSET ?
            """,
                [user_id, user_id, user_id, *condition_params, limit, offset],
            )
        ).fetchall()
        if not rows:
            return []
        dish_ids = [int(row[0]) for row in rows]
        placeholders = ",".join("?" for _ in dish_ids)
        ingredient_rows = await (
            await db.execute(
                f"""SELECT di.dish_id, i.id, i.name, i.normalized_name, i.category_code
            FROM dish_ingredients di JOIN ingredients i ON i.id=di.ingredient_id
            WHERE di.dish_id IN ({placeholders}) ORDER BY i.normalized_name""",
                dish_ids,
            )
        ).fetchall()
        ingredients: dict[int, list[Ingredient]] = {dish_id: [] for dish_id in dish_ids}
        for row in ingredient_rows:
            ingredients[int(row[0])].append(self._ingredient(row[1:]))
        return [
            Dish(
                id=int(row[0]),
                author_id=int(row[1]),
                author_name=str(row[2]),
                name=str(row[3]),
                normalized_name=str(row[4]),
                meal_type=MealType(str(row[5])),
                ingredients=tuple(ingredients[int(row[0])]),
                is_favorite=bool(row[6]),
            )
            for row in rows
        ]

    async def _set_user_ingredient(
        self, table: str, user_id: int, ingredient_id: int, enabled: bool
    ) -> None:
        if table not in {"basic_ingredients", "favorite_ingredients"}:
            raise ValueError("Unsupported table")
        async with self.database.connect() as db:
            if enabled:
                await db.execute(
                    f"INSERT OR IGNORE INTO {table}(user_id, ingredient_id) VALUES (?, ?)",
                    (user_id, ingredient_id),
                )
            else:
                await db.execute(
                    f"DELETE FROM {table} WHERE user_id=? AND ingredient_id=?",
                    (user_id, ingredient_id),
                )
            await db.commit()

    async def _get_user_ingredient_ids(self, table: str, user_id: int) -> set[int]:
        if table not in {"basic_ingredients", "favorite_ingredients"}:
            raise ValueError("Unsupported table")
        async with self.database.connect() as db:
            rows = await (
                await db.execute(f"SELECT ingredient_id FROM {table} WHERE user_id=?", (user_id,))
            ).fetchall()
            return {int(row[0]) for row in rows}

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _ingredient(row: Any) -> Ingredient:
        return Ingredient(int(row[0]), str(row[1]), str(row[2]), str(row[3]))

    @staticmethod
    def _datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace(" ", "T"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
