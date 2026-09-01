from datetime import UTC, datetime, timedelta

import pytest

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import AccessDeniedError, InvalidInviteError, NotFoundError
from what_to_eat_bot.domain.models import MealType
from what_to_eat_bot.repositories.app import AppRepository


async def test_family_join_shared_access_author_acl_and_leave(repository: AppRepository) -> None:
    for user_id, name in [(1, "Алексей"), (2, "Мария"), (3, "Чужой")]:
        await repository.ensure_user(user_id, name)
    chicken = await repository.resolve_ingredient("курица")
    assert chicken
    dish_id = await repository.create_dish(1, "Курица", "курица", MealType.MAIN, [chicken.id])
    await repository.create_family(1, "Дом")
    service = MealService(repository)
    token = await service.create_family_invite(1)
    info = await service.inspect_family_invite(token)
    assert info.family_name == "Дом" and info.inviter_name == "Алексей"
    await service.accept_family_invite(2, token)
    assert (await repository.get_dish(2, dish_id)).author_name == "Алексей"
    with pytest.raises(AccessDeniedError):
        await repository.update_dish(2, dish_id, "Нет", "нет", MealType.MAIN, [chicken.id])
    with pytest.raises(NotFoundError):
        await repository.get_dish(3, dish_id)
    assert await repository.leave_family(2)
    with pytest.raises(NotFoundError):
        await repository.get_dish(2, dish_id)
    assert (await repository.get_dish(1, dish_id)).id == dish_id
    with pytest.raises(InvalidInviteError):
        await service.accept_family_invite(3, token)


async def test_expired_and_invalid_invites(repository: AppRepository) -> None:
    await repository.ensure_user(1, "Алексей")
    await repository.ensure_user(2, "Мария")
    await repository.create_family(1, "Дом")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = MealService(repository, invite_ttl_hours=1, clock=lambda: now)
    token = await service.create_family_invite(1)
    expired_service = MealService(repository, clock=lambda: now + timedelta(hours=2))
    with pytest.raises(InvalidInviteError):
        await expired_service.inspect_family_invite(token)
    with pytest.raises(InvalidInviteError):
        await expired_service.inspect_family_invite("not-a-token")
