import pytest

from what_to_eat_bot.domain.errors import AccessDeniedError, ConflictError, NotFoundError
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.repositories.app import AppRepository


async def seed_users(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    await repository.ensure_user(2, "Мария")
    await repository.ensure_user(3, "Чужой")


async def test_alias_resolution_search_and_duplicate_prevention(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    canonical = await repository.resolve_ingredient("курица")
    alias = await repository.resolve_ingredient("филе курицы")
    assert canonical is not None and alias is not None and canonical.id == alias.id
    found = await repository.search_ingredients("кур")
    assert canonical.id in {item.id for item in found}
    with pytest.raises(ConflictError):
        await repository.create_ingredient("Курица", "курица", 1)


async def test_dish_crud_and_personal_isolation(repository: AppRepository) -> None:
    await seed_users(repository)
    chicken = await repository.resolve_ingredient("курица")
    onion = await repository.resolve_ingredient("лук")
    assert chicken and onion
    dish_id = await repository.create_dish(
        1, "Куриный суп", "куриный суп", MealType.MAIN, [chicken.id, onion.id, onion.id]
    )
    dish = await repository.get_dish(1, dish_id)
    assert dish.name == "Куриный суп" and len(dish.ingredients) == 2
    with pytest.raises(NotFoundError):
        await repository.get_dish(2, dish_id)
    with pytest.raises(AccessDeniedError):
        await repository.update_dish(2, dish_id, "Чужое", "чужое", MealType.MAIN, [chicken.id])
    await repository.update_dish(
        1, dish_id, "Суп с курицей", "суп с курицей", MealType.MAIN, [chicken.id]
    )
    assert (await repository.search_ingredients("груд"))[0].id == chicken.id
    assert [d.name for d in await repository.list_dishes(1, query="суп")] == ["Суп с курицей"]
    assert not await repository.delete_dish(2, dish_id)
    assert await repository.delete_dish(1, dish_id)
    assert not await repository.delete_dish(1, dish_id)


async def test_search_treats_sql_wildcards_as_literal(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    salt = await repository.resolve_ingredient("соль")
    assert salt
    await repository.create_dish(1, "Суп 100%", "суп 100%", MealType.MAIN, [salt.id])
    created = await repository.create_ingredient("Соус 100%", "соус 100%", 1)
    assert [dish.name for dish in await repository.list_dishes(1, query="%")] == ["Суп 100%"]
    assert await repository.list_dishes(1, query="_") == []
    assert [item.id for item in await repository.search_ingredients("соус 100%")] == [created.id]


async def test_favorites_filter_by_type_and_history(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    egg = await repository.resolve_ingredient("яйца")
    rice = await repository.resolve_ingredient("рис")
    assert egg and rice
    breakfast = await repository.create_dish(1, "Омлет", "омлет", MealType.BREAKFAST, [egg.id])
    await repository.create_dish(1, "Рис", "рис", MealType.MAIN, [rice.id])
    assert await repository.toggle_favorite_dish(1, breakfast)
    assert [d.name for d in await repository.list_dishes(1, favorites_only=True)] == ["Омлет"]
    assert [d.name for d in await repository.list_dishes(1, MealType.MAIN)] == ["Рис"]
    await repository.mark_cooked(1, breakfast)
    history = await repository.recent_cooked(1)
    assert history[0][0].id == breakfast


async def test_user_ingredient_settings_can_be_added_and_removed(
    repository: AppRepository,
) -> None:
    await repository.ensure_user(1, "Алексей")
    salt = await repository.resolve_ingredient("соль")
    assert salt
    await repository.set_basic_ingredient(1, salt.id, True)
    await repository.set_favorite_ingredient(1, salt.id, True)
    assert await repository.get_basic_ingredient_ids(1) == {salt.id}
    assert await repository.get_favorite_ingredient_ids(1) == {salt.id}
    await repository.set_basic_ingredient(1, salt.id, False)
    await repository.set_favorite_ingredient(1, salt.id, False)
    assert await repository.get_basic_ingredient_ids(1) == set()
    assert await repository.get_favorite_ingredient_ids(1) == set()
