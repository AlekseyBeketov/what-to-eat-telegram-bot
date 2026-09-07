from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    MAIN = "main"


class ProposalStatus(StrEnum):
    OPEN = "open"
    AGREED = "agreed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


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


@dataclass(frozen=True, slots=True)
class FamilyProposalRecipient:
    user_id: int
    name: str
    accepted: bool | None = None
    message_id: int | None = None


@dataclass(frozen=True, slots=True)
class FamilyMealProposal:
    id: int
    family_id: int
    dish_id: int | None
    proposer_id: int
    proposer_name: str
    dish_name: str
    meal_type: MealType
    ingredient_names: tuple[str, ...]
    status: ProposalStatus
    expires_at: datetime
    proposer_message_id: int | None = None
    recipients: tuple[FamilyProposalRecipient, ...] = field(default_factory=tuple)
