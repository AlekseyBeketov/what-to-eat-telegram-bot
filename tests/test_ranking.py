from datetime import UTC, datetime
from random import Random

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.repositories.app import AppRepository


async def test_ranking_main_product_partial_full_basic_and_type(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    chicken = await repository.resolve_ingredient("курица")
    onion = await repository.resolve_ingredient("лук")
    carrot = await repository.resolve_ingredient("морковь")
    salt = await repository.resolve_ingredient("соль")
    egg = await repository.resolve_ingredient("яйца")
    assert chicken and onion and carrot and salt and egg
    full = await repository.create_dish(
        1,
        "Полное",
        "полное",
        MealType.MAIN,
        [chicken.id, onion.id, carrot.id, salt.id],
    )
    partial = await repository.create_dish(
        1, "Частичное", "частичное", MealType.MAIN, [chicken.id, onion.id]
    )
    await repository.toggle_favorite_dish(1, partial)
    await repository.create_dish(1, "Без курицы", "без курицы", MealType.MAIN, [onion.id])
    await repository.create_dish(1, "Завтрак", "завтрак", MealType.BREAKFAST, [chicken.id, egg.id])
    await repository.set_basic_ingredient(1, salt.id, True)
    service = MealService(repository, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    result = await service.recommend(1, [onion.id, carrot.id], chicken.id, MealType.MAIN)
    assert [item.dish.id for item in result] == [full, result[1].dish.id]
    assert [item.name for item in result[0].matched] == ["Курица", "Лук", "Морковь"]
    assert result[0].missing == ()
    assert all(chicken.id in {i.id for i in item.dish.ingredients} for item in result)
    assert all(item.dish.meal_type is MealType.MAIN for item in result)


async def test_suggestions_avoid_immediate_repeats(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    egg = await repository.resolve_ingredient("яйца")
    assert egg
    for index in range(6):
        await repository.create_dish(
            1, f"Блюдо {index}", f"блюдо {index}", MealType.BREAKFAST, [egg.id]
        )
    service = MealService(repository, random=Random(42))
    first = await service.suggest(1, MealType.BREAKFAST, limit=3)
    second = await service.suggest(1, MealType.BREAKFAST, [d.id for d in first], limit=3)
    assert {d.id for d in first}.isdisjoint({d.id for d in second})


async def test_ranking_treats_all_selected_products_equally(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    chicken = await repository.resolve_ingredient("курица")
    onion = await repository.resolve_ingredient("лук")
    fish = await repository.resolve_ingredient("рыба")
    assert chicken and onion and fish

    full = await repository.create_dish(
        1, "Курица с луком", "курица с луком", MealType.MAIN, [chicken.id, onion.id]
    )
    partial = await repository.create_dish(
        1, "Только курица", "только курица", MealType.MAIN, [chicken.id]
    )
    await repository.create_dish(1, "Только рыба", "только рыба", MealType.MAIN, [fish.id])

    result = await MealService(repository).recommend(
        1,
        [chicken.id, onion.id],
        None,
        MealType.MAIN,
    )

    assert [item.dish.id for item in result] == [full, partial]
    assert [item.name for item in result[0].matched] == ["Курица", "Лук"]
