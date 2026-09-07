import asyncio
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from what_to_eat_bot.application.service import MealService
from what_to_eat_bot.domain.errors import DomainError
from what_to_eat_bot.domain.models import Dish, FamilyMealProposal, MealType, ProposalStatus
from what_to_eat_bot.handlers.keyboards import buttons
from what_to_eat_bot.handlers.presentation import MEAL_TYPE_LABELS, PAGE_SIZE
from what_to_eat_bot.repositories.app import AppRepository

router = Router(name="family_proposals")
logger = logging.getLogger(__name__)


def _meal_phrase(meal_type: MealType) -> str:
    return "на завтрак" if meal_type is MealType.BREAKFAST else "на обед/ужин"


def _ingredients_text(names: tuple[str, ...]) -> str:
    visible = "\n".join(f"• {escape(name)}" for name in names[:PAGE_SIZE])
    if len(names) > PAGE_SIZE:
        visible += f"\n• … ещё {len(names) - PAGE_SIZE}"
    return visible or "• Не указаны"


def _proposal_confirmation_text(dish: Dish) -> str:
    return (
        "<b>Предложить семье блюдо на сегодня?</b>\n\n"
        f"{MEAL_TYPE_LABELS[dish.meal_type]}\n"
        f"<b>{escape(dish.name)}</b>\n\n"
        "После подтверждения сообщение получат все остальные участники семьи."
    )


def _recipient_text(proposal: FamilyMealProposal, accepted: bool | None = None) -> str:
    text = (
        "🍽 <b>Предложение на сегодня</b>\n\n"
        f"{escape(proposal.proposer_name)} предлагает приготовить\n"
        f"{_meal_phrase(proposal.meal_type)}:\n\n"
        f"<b>{escape(proposal.dish_name)}</b>\n\n"
        f"<b>Ингредиенты:</b>\n{_ingredients_text(proposal.ingredient_names)}\n\n"
        "Согласны приготовить это блюдо?"
    )
    if accepted is not None:
        answer = "✅ Согласен(на)" if accepted else "❌ Не согласен(на)"
        text += f"\n\nВаш ответ: <b>{answer}</b>"
    return text


def _vote_markup(proposal_id: int):
    return buttons(
        [
            [
                ("✅ Согласен(на)", f"proposal:vote:{proposal_id}:yes"),
                ("❌ Не согласен(на)", f"proposal:vote:{proposal_id}:no"),
            ]
        ]
    )


def _sender_status_text(proposal: FamilyMealProposal) -> str:
    agreed = sum(item.accepted is True for item in proposal.recipients)
    declined = sum(item.accepted is False for item in proposal.recipients)
    answered = agreed + declined
    return (
        "📨 <b>Предложение отправлено семье</b>\n\n"
        f"Вы предлагаете сегодня приготовить {_meal_phrase(proposal.meal_type)}:\n\n"
        f"<b>{escape(proposal.dish_name)}</b>\n\n"
        "Ваш ответ уже считается положительным.\n\n"
        f"Ответили: {answered} из {len(proposal.recipients)}\n"
        f"✅ Согласны: {agreed}\n"
        f"❌ Не согласны: {declined}"
    )


def _final_text(proposal: FamilyMealProposal) -> str:
    return (
        "🎉 <b>Договорились!</b>\n\n"
        f"Сегодня {_meal_phrase(proposal.meal_type)} готовим\n"
        f"<b>{escape(proposal.dish_name)}</b>."
    )


def _sender_final_text(proposal: FamilyMealProposal) -> str:
    names = "\n".join(
        f"• {escape(name)}"
        for name in [proposal.proposer_name, *(item.name for item in proposal.recipients)]
    )
    return _final_text(proposal) + f"\n\n<b>Согласны:</b>\n{names}"


def _expired_text(proposal: FamilyMealProposal) -> str:
    return (
        "⌛ Предложение приготовить "
        f"«{escape(proposal.dish_name)}» {_meal_phrase(proposal.meal_type)} больше неактуально."
    )


async def _edit_sender_message(
    bot: Bot,
    proposal: FamilyMealProposal,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    if proposal.proposer_message_id is None:
        return False
    try:
        await bot.edit_message_text(
            chat_id=proposal.proposer_id,
            message_id=proposal.proposer_message_id,
            text=text,
            reply_markup=reply_markup,
        )
        return True
    except TelegramAPIError:
        logger.warning(
            "Could not update proposal author message",
            extra={"proposal_id": proposal.id, "user_id": proposal.proposer_id},
        )
        return False


async def _remove_recipient_buttons(bot: Bot, proposal: FamilyMealProposal) -> None:
    for recipient in proposal.recipients:
        if recipient.message_id is None:
            continue
        try:
            await bot.edit_message_reply_markup(
                chat_id=recipient.user_id,
                message_id=recipient.message_id,
                reply_markup=None,
            )
        except TelegramAPIError:
            logger.warning(
                "Could not remove proposal buttons",
                extra={"proposal_id": proposal.id, "user_id": recipient.user_id},
            )


@router.callback_query(F.data.startswith("dish:propose:"))
async def propose_prompt(callback: CallbackQuery, repository: AppRepository) -> None:
    dish_id = int((callback.data or "").rsplit(":", 1)[-1])
    try:
        dish = await repository.get_dish(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return
    family = await repository.family_info(callback.from_user.id)
    if not family:
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "Чтобы предлагать блюда семье, сначала создайте семью "
                "или вступите в уже существующую.",
                reply_markup=buttons([[("👨‍👩‍👧 Открыть настройки семьи", "family:menu")]]),
            )
        return
    if len(family[2]) < 2:
        await callback.answer("В семье пока нет других участников", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            _proposal_confirmation_text(dish),
            reply_markup=buttons(
                [
                    [
                        ("✅ Да, отправить", f"proposal:send:{dish.id}"),
                        ("❌ Отмена", "proposal:dismiss"),
                    ]
                ]
            ),
        )


@router.callback_query(F.data == "proposal:dismiss")
async def dismiss_proposal(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_text("Предложение не отправлено.")  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("proposal:send:"))
async def send_proposal(callback: CallbackQuery, bot: Bot, service: MealService) -> None:
    dish_id = int((callback.data or "").rsplit(":", 1)[-1])
    try:
        proposal = await service.create_family_proposal(callback.from_user.id, dish_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.answer("Отправляю предложение семье…")
    sender_message_id = getattr(callback.message, "message_id", None)
    if sender_message_id is not None:
        await service.record_family_proposal_sender_message(
            proposal.id, callback.from_user.id, sender_message_id
        )
    delivered = [recipient for recipient in proposal.recipients if recipient.message_id is not None]
    failed = []
    for recipient in proposal.recipients:
        if recipient.message_id is not None:
            continue
        try:
            message = await bot.send_message(
                recipient.user_id,
                _recipient_text(proposal),
                reply_markup=_vote_markup(proposal.id),
            )
            await service.record_family_proposal_message(
                proposal.id, recipient.user_id, message.message_id
            )
            delivered.append(recipient)
        except TelegramAPIError:
            failed.append(recipient)
            logger.warning(
                "Could not deliver family proposal",
                extra={"proposal_id": proposal.id, "user_id": recipient.user_id},
            )

    if failed:
        cancelled = await service.cancel_family_proposal(callback.from_user.id, proposal.id)
        await _remove_recipient_buttons(bot, cancelled)
        for recipient in delivered:
            try:
                await bot.send_message(
                    recipient.user_id,
                    "🚫 Предложение отменено: бот не смог доставить его всей семье.",
                )
            except TelegramAPIError:
                logger.warning(
                    "Could not notify recipient about cancelled proposal",
                    extra={"proposal_id": proposal.id, "user_id": recipient.user_id},
                )
        names = ", ".join(escape(item.name) for item in failed)
        if callback.message:
            await callback.message.edit_text(  # type: ignore[union-attr]
                "Не удалось доставить предложение следующим участникам:\n"
                f"{names}\n\nПредложение отменено."
            )
        return

    proposal = await service.get_family_proposal(callback.from_user.id, proposal.id)
    if callback.message:
        try:
            if proposal.status is ProposalStatus.AGREED:
                await _remove_recipient_buttons(bot, proposal)
                await callback.message.edit_text(  # type: ignore[union-attr]
                    _sender_final_text(proposal), reply_markup=None
                )
            elif proposal.status is ProposalStatus.OPEN:
                await callback.message.edit_text(  # type: ignore[union-attr]
                    _sender_status_text(proposal),
                    reply_markup=buttons(
                        [[("❌ Отменить предложение", f"proposal:cancel:{proposal.id}")]]
                    ),
                )
            elif proposal.status is ProposalStatus.EXPIRED:
                await callback.message.edit_text(  # type: ignore[union-attr]
                    _expired_text(proposal), reply_markup=None
                )
            else:
                await callback.message.edit_text(  # type: ignore[union-attr]
                    f"🚫 Предложение приготовить «{escape(proposal.dish_name)}» отменено.",
                    reply_markup=None,
                )
        except TelegramAPIError:
            logger.warning(
                "Could not update proposal send status",
                extra={"proposal_id": proposal.id, "user_id": proposal.proposer_id},
            )


@router.callback_query(F.data.startswith("proposal:vote:"))
async def vote_proposal(callback: CallbackQuery, bot: Bot, service: MealService) -> None:
    parts = (callback.data or "").split(":")
    proposal_id = int(parts[2])
    accepted = parts[3] == "yes"
    try:
        proposal, changed = await service.respond_to_family_proposal(
            callback.from_user.id, proposal_id, accepted
        )
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
        return

    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            _recipient_text(proposal, accepted),
            reply_markup=(
                _vote_markup(proposal.id) if proposal.status is ProposalStatus.OPEN else None
            ),
        )
    await callback.answer(
        "Ответ отправлен: согласен ✅" if accepted else "Ответ отправлен: не согласен ❌"
    )
    if not changed:
        return

    member = next(item for item in proposal.recipients if item.user_id == callback.from_user.id)
    response_text = (
        f"✅ {escape(member.name)} поддерживает предложение приготовить "
        if accepted
        else f"❌ {escape(member.name)} не поддерживает предложение приготовить "
    )
    try:
        await bot.send_message(
            proposal.proposer_id,
            response_text + f"«{escape(proposal.dish_name)}» {_meal_phrase(proposal.meal_type)}.",
        )
    except TelegramAPIError:
        logger.warning(
            "Could not notify proposal author",
            extra={"proposal_id": proposal.id, "user_id": proposal.proposer_id},
        )

    if proposal.status is ProposalStatus.OPEN:
        await _edit_sender_message(
            bot,
            proposal,
            _sender_status_text(proposal),
            buttons([[("❌ Отменить предложение", f"proposal:cancel:{proposal.id}")]]),
        )
    elif proposal.status is ProposalStatus.AGREED:
        await _remove_recipient_buttons(bot, proposal)
        sender_updated = await _edit_sender_message(bot, proposal, _sender_final_text(proposal))
        if not sender_updated:
            try:
                await bot.send_message(proposal.proposer_id, _sender_final_text(proposal))
            except TelegramAPIError:
                logger.warning(
                    "Could not deliver final proposal result",
                    extra={"proposal_id": proposal.id, "user_id": proposal.proposer_id},
                )
        for recipient in proposal.recipients:
            try:
                await bot.send_message(recipient.user_id, _final_text(proposal))
            except TelegramAPIError:
                logger.warning(
                    "Could not deliver final proposal result",
                    extra={"proposal_id": proposal.id, "user_id": recipient.user_id},
                )


@router.callback_query(F.data.startswith("proposal:cancel:"))
async def cancel_proposal(callback: CallbackQuery, bot: Bot, service: MealService) -> None:
    proposal_id = int((callback.data or "").rsplit(":", 1)[-1])
    try:
        proposal = await service.cancel_family_proposal(callback.from_user.id, proposal_id)
    except DomainError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.answer("Предложение отменено")
    await _remove_recipient_buttons(bot, proposal)
    cancellation = (
        f"🚫 {escape(proposal.proposer_name)} отменил(а) предложение приготовить "
        f"«{escape(proposal.dish_name)}» {_meal_phrase(proposal.meal_type)}."
    )
    for recipient in proposal.recipients:
        try:
            await bot.send_message(recipient.user_id, cancellation)
        except TelegramAPIError:
            logger.warning(
                "Could not notify recipient about cancellation",
                extra={"proposal_id": proposal.id, "user_id": recipient.user_id},
            )
    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"🚫 Предложение приготовить «{escape(proposal.dish_name)}» отменено."
        )


async def process_expired_proposals(bot: Bot, service: MealService) -> int:
    proposals = await service.expire_family_proposals()
    for proposal in proposals:
        text = _expired_text(proposal)
        await _remove_recipient_buttons(bot, proposal)
        await _edit_sender_message(bot, proposal, text)
        for user_id in [proposal.proposer_id, *(item.user_id for item in proposal.recipients)]:
            try:
                await bot.send_message(user_id, text)
            except TelegramAPIError:
                logger.warning(
                    "Could not notify about expired proposal",
                    extra={"proposal_id": proposal.id, "user_id": user_id},
                )
    return len(proposals)


async def expiration_worker(bot: Bot, service: MealService, interval_seconds: float = 60) -> None:
    while True:
        try:
            await process_expired_proposals(bot, service)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Could not process expired family proposals")
        await asyncio.sleep(interval_seconds)
