from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from random import Random

from what_to_eat_bot.application.normalization import (
    display_name,
    normalize_text,
    parse_ingredient_list,
)
from what_to_eat_bot.domain.errors import ConflictError
from what_to_eat_bot.domain.models import Dish, Ingredient, MealType, Recommendation
from what_to_eat_bot.repositories.app import AppRepository


class MealService:
    def __init__(
        self,
        repository: AppRepository,
        invite_ttl_hours: int = 72,
        clock: Callable[[], datetime] | None = None,
        random: Random | None = None,
    ) -> None:
        self.repository = repository
        self.invite_ttl_hours = invite_ttl_hours
        self._clock = clock or (lambda: datetime.now(UTC))
        self._random = random or Random()

    async def create_dish(
        self, user_id: int, name: str, meal_type: MealType, ingredient_ids: Sequence[int]
    ) -> int:
        normalized = normalize_text(name)
        if len(normalized) < 2:
            raise ConflictError("Название блюда слишком короткое")
        return await self.repository.create_dish(
            user_id, display_name(name), normalized, meal_type, ingredient_ids
        )

    async def update_dish(
        self,
        user_id: int,
        dish_id: int,
        name: str,
        meal_type: MealType,
        ingredient_ids: Sequence[int],
    ) -> None:
        normalized = normalize_text(name)
        if len(normalized) < 2:
            raise ConflictError("Название блюда слишком короткое")
        await self.repository.update_dish(
            user_id,
            dish_id,
            display_name(name),
            normalized,
            meal_type,
            ingredient_ids,
        )

    async def parse_ingredients(self, value: str) -> tuple[list[Ingredient], list[str]]:
        resolved: list[Ingredient] = []
        missing: list[str] = []
        seen: set[int] = set()
        for raw in parse_ingredient_list(value):
            ingredient = await self.repository.resolve_ingredient(normalize_text(raw))
            if ingredient:
                if ingredient.id not in seen:
                    seen.add(ingredient.id)
                    resolved.append(ingredient)
            else:
                missing.append(display_name(raw))
        return resolved, missing

    async def create_ingredient(self, user_id: int, value: str) -> Ingredient:
        normalized = normalize_text(value)
        if len(normalized) < 2:
            raise ConflictError("Название ингредиента слишком короткое")
        existing = await self.repository.resolve_ingredient(normalized)
        if existing:
            return existing
        return await self.repository.create_ingredient(
            display_name(value), normalized, user_id, "other"
        )

    async def search_dishes(
        self, user_id: int, query: str, limit: int = 10, offset: int = 0
    ) -> list[Dish]:
        normalized = normalize_text(query)
        if not normalized:
            return []
        return await self.repository.list_dishes(
            user_id, query=normalized, limit=limit, offset=offset
        )

    async def recommend(
        self,
        user_id: int,
        selected_ids: Iterable[int],
        main_ingredient_id: int | None,
        meal_type: MealType | None = None,
        limit: int = 10,
        offset: int = 0,
        record_usage: bool = True,
    ) -> list[Recommendation]:
        selected = set(selected_ids)
        if main_ingredient_id is not None:
            selected.add(main_ingredient_id)
        basic = await self.repository.get_basic_ingredient_ids(user_id)
        dishes = await self.repository.list_dishes(user_id, meal_type=meal_type, limit=1000)
        recent = await self.repository.last_cooked_by_dish(user_id)
        now = self._clock()
        result: list[Recommendation] = []
        selected_non_basic = selected - basic
        for dish in dishes:
            dish_ids = {item.id for item in dish.ingredients}
            if main_ingredient_id is not None and main_ingredient_id not in dish_ids:
                continue
            if main_ingredient_id is None and not (dish_ids & selected):
                continue
            matched_ids = dish_ids & selected
            missing_ids = dish_ids - selected - basic
            dish_non_basic = dish_ids - basic
            coverage = len(matched_ids & selected_non_basic) / max(1, len(selected_non_basic))
            completeness = len(matched_ids - basic) / max(1, len(dish_non_basic))
            penalty = self._recent_penalty(recent.get(dish.id), now)
            score = 100 * coverage + 25 * completeness + 3 * dish.is_favorite - penalty
            matched = tuple(item for item in dish.ingredients if item.id in matched_ids)
            missing = tuple(item for item in dish.ingredients if item.id in missing_ids)
            result.append(Recommendation(dish, round(score, 4), matched, missing))
        result.sort(
            key=lambda item: (
                -item.score,
                -len(item.matched),
                len(item.missing),
                item.dish.normalized_name,
                item.dish.id,
            )
        )
        if record_usage:
            await self.repository.record_ingredient_usage(user_id, selected)
        return result[offset : offset + limit]

    async def suggest(
        self,
        user_id: int,
        meal_type: MealType | None = None,
        exclude_ids: Iterable[int] = (),
        limit: int | None = None,
    ) -> list[Dish]:
        suggestion_count, _ = await self.repository.get_settings(user_id)
        size = limit or suggestion_count
        dishes = await self.repository.list_dishes(user_id, meal_type=meal_type, limit=1000)
        excluded = set(exclude_ids)
        available = [dish for dish in dishes if dish.id not in excluded]
        if len(available) < size:
            available = dishes
        recent = await self.repository.last_cooked_by_dish(user_id)
        now = self._clock()
        weighted: list[tuple[float, Dish]] = []
        for dish in available:
            age_bonus = 0.0
            cooked = recent.get(dish.id)
            if cooked:
                age_bonus = min(2.0, max(0.0, (now - cooked).days / 30))
            weight = 1.0 + (0.2 if dish.is_favorite else 0.0) + age_bonus
            weighted.append((weight, dish))
        chosen: list[Dish] = []
        pool = weighted[:]
        while pool and len(chosen) < size:
            total = sum(weight for weight, _ in pool)
            point = self._random.random() * total
            cumulative = 0.0
            index = 0
            for candidate_index, (weight, _) in enumerate(pool):
                index = candidate_index
                cumulative += weight
                if cumulative >= point:
                    break
            _, dish = pool.pop(index)
            chosen.append(dish)
        return chosen

    async def create_family_invite(self, user_id: int) -> str:
        token = secrets.token_urlsafe(24)
        await self.repository.create_invite(
            user_id,
            self.hash_invite(token),
            self._clock() + timedelta(hours=self.invite_ttl_hours),
        )
        return token

    async def inspect_family_invite(self, token: str):
        return await self.repository.inspect_invite(self.hash_invite(token), self._clock())

    async def accept_family_invite(self, user_id: int, token: str) -> int:
        return await self.repository.accept_invite(user_id, self.hash_invite(token), self._clock())

    @staticmethod
    def hash_invite(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _recent_penalty(cooked_at: datetime | None, now: datetime) -> int:
        if cooked_at is None:
            return 0
        days = max(0, (now - cooked_at).days)
        if days < 1:
            return 10
        if days < 3:
            return 6
        if days < 7:
            return 3
        return 0
