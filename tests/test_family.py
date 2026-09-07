from datetime import UTC, datetime, timedelta

import pytest

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import (
    AccessDeniedError,
    ConflictError,
    InvalidInviteError,
    NotFoundError,
)
from what_to_eat_bot.domain.models import MealType, ProposalStatus
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


async def test_family_proposal_collects_answers_and_completes_unanimously(
    repository: AppRepository,
) -> None:
    for user_id, name in [(1, "Алексей"), (2, "Мария"), (3, "Иван")]:
        await repository.ensure_user(user_id, name)
    ingredient = await repository.resolve_ingredient("курица")
    assert ingredient
    dish_id = await repository.create_dish(1, "Курица", "курица", MealType.MAIN, [ingredient.id])
    await repository.create_family(1, "Дом")
    service = MealService(repository)
    for user_id in (2, 3):
        token = await service.create_family_invite(1)
        await service.accept_family_invite(user_id, token)

    now = datetime(2026, 1, 1, 20, 30, tzinfo=UTC)
    service = MealService(repository, clock=lambda: now)
    proposal = await service.create_family_proposal(1, dish_id)
    repeated = await service.create_family_proposal(1, dish_id)

    assert repeated.id == proposal.id
    assert proposal.proposer_name == "Алексей"
    assert proposal.dish_name == "Курица"
    assert proposal.ingredient_names == ("Курица",)
    assert proposal.status is ProposalStatus.OPEN
    assert proposal.expires_at == datetime(2026, 1, 1, 21, 0, tzinfo=UTC)
    assert {(item.user_id, item.name) for item in proposal.recipients} == {
        (2, "Мария"),
        (3, "Иван"),
    }

    proposal, changed = await service.respond_to_family_proposal(2, proposal.id, True)
    assert changed is True
    assert proposal.status is ProposalStatus.OPEN

    proposal, changed = await service.respond_to_family_proposal(2, proposal.id, True)
    assert changed is False

    proposal, _ = await service.respond_to_family_proposal(3, proposal.id, False)
    assert proposal.status is ProposalStatus.OPEN
    proposal, changed = await service.respond_to_family_proposal(3, proposal.id, True)
    assert changed is True
    assert proposal.status is ProposalStatus.AGREED
    assert all(item.accepted is True for item in proposal.recipients)


async def test_family_proposal_requires_other_members_and_authorizes_responses(
    repository: AppRepository,
) -> None:
    for user_id, name in [(1, "Алексей"), (2, "Мария"), (3, "Чужой")]:
        await repository.ensure_user(user_id, name)
    ingredient = await repository.resolve_ingredient("курица")
    assert ingredient
    dish_id = await repository.create_dish(1, "Курица", "курица", MealType.MAIN, [ingredient.id])
    await repository.create_family(1, "Дом")
    service = MealService(repository)

    with pytest.raises(ConflictError, match="других участников"):
        await service.create_family_proposal(1, dish_id)

    token = await service.create_family_invite(1)
    await service.accept_family_invite(2, token)
    proposal = await service.create_family_proposal(1, dish_id)

    with pytest.raises(AccessDeniedError):
        await service.respond_to_family_proposal(3, proposal.id, True)

    cancelled = await service.cancel_family_proposal(1, proposal.id)
    assert cancelled.status is ProposalStatus.CANCELLED


async def test_expired_family_proposal_rejects_vote_and_can_be_replaced(
    repository: AppRepository,
) -> None:
    for user_id, name in [(1, "Алексей"), (2, "Мария")]:
        await repository.ensure_user(user_id, name)
    ingredient = await repository.resolve_ingredient("курица")
    assert ingredient
    dish_id = await repository.create_dish(1, "Курица", "курица", MealType.MAIN, [ingredient.id])
    await repository.create_family(1, "Дом")
    invite_service = MealService(repository)
    token = await invite_service.create_family_invite(1)
    await invite_service.accept_family_invite(2, token)

    service = MealService(
        repository,
        clock=lambda: datetime(2026, 1, 1, 20, 30, tzinfo=UTC),
    )
    expired = await service.create_family_proposal(1, dish_id)
    next_day_service = MealService(
        repository,
        clock=lambda: datetime(2026, 1, 1, 21, 0, tzinfo=UTC),
    )

    expired_proposals = await next_day_service.expire_family_proposals()
    assert [item.id for item in expired_proposals] == [expired.id]
    assert expired_proposals[0].status is ProposalStatus.EXPIRED
    assert await next_day_service.expire_family_proposals() == []

    with pytest.raises(ConflictError, match="завершено"):
        await next_day_service.respond_to_family_proposal(2, expired.id, True)

    replacement = await next_day_service.create_family_proposal(1, dish_id)
    assert replacement.id != expired.id
