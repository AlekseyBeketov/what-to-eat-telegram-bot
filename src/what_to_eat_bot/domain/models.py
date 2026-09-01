from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    MAIN = "main"


@dataclass(frozen=True, slots=True)
class Ingredient:
    id: int
    name: str
    normalized_name: str
    category: str


@dataclass(frozen=True, slots=True)
class Dish:
    id: int
    author_id: int
    author_name: str
    name: str
    normalized_name: str
    meal_type: MealType
    ingredients: tuple[Ingredient, ...] = field(default_factory=tuple)
    is_favorite: bool = False


@dataclass(frozen=True, slots=True)
class Recommendation:
    dish: Dish
    score: float
    matched: tuple[Ingredient, ...]
    missing: tuple[Ingredient, ...]


@dataclass(frozen=True, slots=True)
class FamilyInvite:
    family_id: int
    family_name: str
    inviter_name: str
    expires_at: datetime
