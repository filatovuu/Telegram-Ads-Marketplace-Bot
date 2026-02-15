"""Fire-and-forget Telegram notifications for deal events.

Sends messages via Bot API (httpx). Exceptions are caught and logged —
notifications never break the main flow.
"""

import logging

import httpx
from sqlalchemy import or_, select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.deal_state_machine import (
    MESSAGING_STATUSES,
    DealStatus,
    get_available_actions,
)

logger = logging.getLogger(__name__)

_STATUS_TEMPLATES = {
    "en": {
        "NEGOTIATION": "Deal #{deal_id}: sent for negotiation. Price: {price} {currency}.",
        "OWNER_ACCEPTED": "Deal #{deal_id}: the channel owner accepted the deal.",
        "AWAITING_ESCROW_PAYMENT": f"Deal #{{deal_id}}: awaiting escrow payment of {{price}} {{currency}}. Deposit within {settings.deal_expire_hours}h or the deal will expire.",
        "ESCROW_FUNDED": "Deal #{deal_id}: escrow of {price} {currency} has been funded.",
        "CREATIVE_PENDING_OWNER": "Deal #{deal_id}: waiting for creative from channel owner.",
        "CREATIVE_SUBMITTED": "Deal #{deal_id}: creative has been submitted for review.",
        "CREATIVE_CHANGES_REQUESTED": "Deal #{deal_id}: changes requested for the creative.",
        "CREATIVE_APPROVED": "Deal #{deal_id}: creative approved!",
        "SCHEDULED": "Deal #{deal_id}: post has been scheduled.",
        "POSTED": "Deal #{deal_id}: post has been published.",
        "RETENTION_CHECK": "Deal #{deal_id}: retention check in progress.",
        "RELEASED": "Deal #{deal_id}: payment release requested. Processing on-chain transfer...",
        "REFUNDED": "Deal #{deal_id}: refund requested. Processing on-chain transfer...",
        "CANCELLED": "Deal #{deal_id}: deal has been cancelled.",
        "EXPIRED": "Deal #{deal_id}: deal has expired due to inactivity.",
    },
    "ru": {
        "NEGOTIATION": "Сделка #{deal_id}: отправлена на обсуждение. Цена: {price} {currency}.",
        "OWNER_ACCEPTED": "Сделка #{deal_id}: владелец канала принял сделку.",
        "AWAITING_ESCROW_PAYMENT": f"Сделка #{{deal_id}}: ожидание оплаты эскроу на сумму {{price}} {{currency}}. Внесите депозит в течение {settings.deal_expire_hours} ч. или сделка истечёт.",
        "ESCROW_FUNDED": "Сделка #{deal_id}: эскроу на сумму {price} {currency} пополнен.",
        "CREATIVE_PENDING_OWNER": "Сделка #{deal_id}: ожидание креатива от владельца канала.",
        "CREATIVE_SUBMITTED": "Сделка #{deal_id}: креатив отправлен на проверку.",
        "CREATIVE_CHANGES_REQUESTED": "Сделка #{deal_id}: запрошены изменения в креативе.",
        "CREATIVE_APPROVED": "Сделка #{deal_id}: креатив одобрен!",
        "SCHEDULED": "Сделка #{deal_id}: пост запланирован.",
        "POSTED": "Сделка #{deal_id}: пост опубликован.",
        "RETENTION_CHECK": "Сделка #{deal_id}: проверка удержания.",
        "RELEASED": "Сделка #{deal_id}: запрошен перевод оплаты. Обработка транзакции...",
        "REFUNDED": "Сделка #{deal_id}: запрошен возврат средств. Обработка транзакции...",
        "CANCELLED": "Сделка #{deal_id}: сделка отменена.",
        "EXPIRED": "Сделка #{deal_id}: сделка истекла из-за неактивности.",
    },
}

_MESSAGE_TEMPLATE = {
    "en": "Deal #{deal_id}: new message from {sender_name}:\n\n{text}",
    "ru": "Сделка #{deal_id}: новое сообщение от {sender_name}:\n\n{text}",
}

# Human-readable action labels for inline buttons
_ACTION_LABELS = {
    "en": {
        "send": "Send to Owner",
        "accept": "Accept",
        "request_escrow": "Request Escrow",
        "confirm_escrow": "Confirm Escrow",
        "request_creative": "Request Creative",
        "submit_creative": "Submit Creative",
        "approve_creative": "Approve Creative",
        "request_changes": "Request Changes",
        "schedule": "Schedule",
        "mark_posted": "Mark Posted",
        "start_retention": "Start Retention",
        "release": "Release Payment",
        "refund": "Refund",
        "cancel": "Cancel Deal",
        "expire": "Expire",
    },
    "ru": {
        "send": "Отправить владельцу",
        "accept": "Принять",
        "request_escrow": "Запросить эскроу",
        "confirm_escrow": "Подтвердить эскроу",
        "request_creative": "Запросить креатив",
        "submit_creative": "Отправить креатив",
        "approve_creative": "Одобрить креатив",
        "request_changes": "Запросить изменения",
        "schedule": "Запланировать",
        "mark_posted": "Отметить опубл.",
        "start_retention": "Начать проверку",
        "release": "Выплатить",
        "refund": "Возврат",
        "cancel": "Отменить сделку",
        "expire": "Истечь",
    },
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _send_telegram_message(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = None,
) -> None:
    """Send a message via Telegram Bot API with retry."""
    if not settings.bot_token:
        logger.warning("BOT_TOKEN not set, skipping notification")
        return

    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Telegram sendMessage failed: %s", resp.text)


_MEDIA_METHODS = {
    "photo": "sendPhoto",
    "video": "sendVideo",
    "document": "sendDocument",
    "animation": "sendAnimation",
}

_MEDIA_FIELD = {
    "photo": "photo",
    "video": "video",
    "document": "document",
    "animation": "animation",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _send_telegram_media(
    chat_id: int,
    media_url: str,
    media_type: str,
    caption: str | None = None,
    reply_markup: dict | None = None,
) -> None:
    """Send a media message via Telegram Bot API with retry."""
    if not settings.bot_token:
        logger.warning("BOT_TOKEN not set, skipping notification")
        return

    method = _MEDIA_METHODS.get(media_type)
    if not method:
        logger.warning("Unknown media_type %s, falling back to text", media_type)
        await _send_telegram_message(chat_id, caption or "", reply_markup=reply_markup)
        return

    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    field = _MEDIA_FIELD[media_type]
    payload: dict = {"chat_id": chat_id, field: media_url}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Telegram %s failed: %s", method, resp.text)


_INPUT_MEDIA_TYPE = {
    "photo": "InputMediaPhoto",
    "video": "InputMediaVideo",
    "document": "InputMediaDocument",
    "animation": "InputMediaAnimation",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _send_telegram_media_group(
    chat_id: int,
    media_items: list[dict],
    caption: str | None = None,
) -> None:
    """Send a media group (album) via Telegram Bot API.

    Note: sendMediaGroup does not support reply_markup. The caller should
    send a follow-up text message with the keyboard.
    """
    if not settings.bot_token:
        logger.warning("BOT_TOKEN not set, skipping notification")
        return

    media = []
    for i, item in enumerate(media_items):
        media_type = item.get("type", "photo")
        input_type = _INPUT_MEDIA_TYPE.get(media_type)
        if not input_type:
            continue
        entry: dict = {"type": media_type, "media": item["file_id"]}
        if i == 0 and caption:
            entry["caption"] = caption
        media.append(entry)

    if not media:
        return

    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMediaGroup"
    payload: dict = {"chat_id": chat_id, "media": media}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Telegram sendMediaGroup failed: %s", resp.text)


def _get_locale(user) -> str:
    """Get user locale, defaulting to 'en'."""
    locale = getattr(user, "locale", "en") or "en"
    return locale if locale in _STATUS_TEMPLATES else "en"


_ALL_TEAM_PERMISSIONS = ["can_accept_deals", "can_post", "can_payout"]

# Map deal status → team permissions whose holders should be notified.
_STATUS_TEAM_PERMISSIONS: dict[str, list[str]] = {
    "NEGOTIATION": ["can_accept_deals"],
    "OWNER_ACCEPTED": ["can_accept_deals"],
    "AWAITING_ESCROW_PAYMENT": ["can_accept_deals", "can_payout"],
    "ESCROW_FUNDED": ["can_accept_deals", "can_post"],
    "CREATIVE_PENDING_OWNER": ["can_post"],
    "CREATIVE_SUBMITTED": ["can_post"],
    "CREATIVE_CHANGES_REQUESTED": ["can_post"],
    "CREATIVE_APPROVED": ["can_post"],
    "SCHEDULED": ["can_post"],
    "POSTED": ["can_post"],
    "RETENTION_CHECK": ["can_post"],
    "RELEASED": _ALL_TEAM_PERMISSIONS,
    "REFUNDED": _ALL_TEAM_PERMISSIONS,
    "CANCELLED": _ALL_TEAM_PERMISSIONS,
    "EXPIRED": _ALL_TEAM_PERMISSIONS,
}


async def _get_team_recipients(
    deal,
    *,
    permission: str | None = None,
    permissions: list[str] | None = None,
):
    """Return team members for the deal's channel, optionally filtered by permission flag(s).

    When *permissions* list is provided, members matching ANY of the flags are returned (OR).
    Single *permission* param is kept for backward compatibility.
    Excludes the channel owner (already notified separately).
    """
    from app.db.session import async_session_factory
    from app.models.channel_team import ChannelTeamMember

    listing = getattr(deal, "listing", None)
    if listing is None:
        return []
    channel_id = listing.channel_id

    # Merge single + list params
    perm_flags = list(permissions or [])
    if permission and permission not in perm_flags:
        perm_flags.append(permission)

    async with async_session_factory() as db:
        q = select(ChannelTeamMember).where(
            ChannelTeamMember.channel_id == channel_id,
            ChannelTeamMember.user_id != deal.owner_id,
        )
        if perm_flags:
            q = q.where(
                or_(
                    *(
                        getattr(ChannelTeamMember, p) == True  # noqa: E712
                        for p in perm_flags
                    )
                )
            )
        result = await db.execute(q)
        members = result.scalars().all()
        # Eagerly access user relationship while session is open
        for m in members:
            _ = m.user
        return members


def _build_deal_keyboard(deal, actor: str, lang: str) -> dict | None:
    """Build an inline keyboard with available deal actions for this actor."""
    actions = get_available_actions(deal.status, actor)

    # Hide "accept" from the deal creator — only the counter-party can accept
    if deal.status == "NEGOTIATION" and "accept" in actions:
        is_creator = (deal.campaign_id is not None and actor == "owner") or (
            deal.campaign_id is None and actor == "advertiser"
        )
        if is_creator:
            actions = [a for a in actions if a != "accept"]
    if not actions:
        # No transition actions — still add messaging button if allowed
        try:
            current = DealStatus(deal.status)
        except ValueError:
            return None
        buttons = []
        if current in MESSAGING_STATUSES:
            buttons.append(
                [
                    {"text": "Send Message", "callback_data": f"deal_msg:{deal.id}"},
                ]
            )
        # Add "Propose Changes" for owner in NEGOTIATION
        if actor == "owner" and deal.status == "NEGOTIATION":
            propose_label = (
                "Propose Changes" if lang == "en" else "Предложить изменения"
            )
            buttons.append(
                [{"text": propose_label, "callback_data": f"amend_propose:{deal.id}"}]
            )
        # Add "View Deal" web_app button
        if settings.mini_app_url:
            view_label = "View Deal" if lang == "en" else "Открыть сделку"
            buttons.append(
                [
                    {
                        "text": view_label,
                        "web_app": {"url": f"{settings.mini_app_url}/deals/{deal.id}"},
                    }
                ]
            )
        return {"inline_keyboard": buttons} if buttons else None

    labels = _ACTION_LABELS.get(lang, _ACTION_LABELS["en"])
    buttons = []
    for action in actions:
        label = labels.get(action, action)
        callback_data = f"deal:{deal.id}:{action}"
        if len(callback_data) > 64:
            continue
        buttons.append([{"text": label, "callback_data": callback_data}])

    # Add "Propose Changes" for owner in NEGOTIATION
    if actor == "owner" and deal.status == "NEGOTIATION":
        propose_label = "Propose Changes" if lang == "en" else "Предложить изменения"
        buttons.append(
            [{"text": propose_label, "callback_data": f"amend_propose:{deal.id}"}]
        )

    # Add messaging button if status allows
    try:
        current = DealStatus(deal.status)
    except ValueError:
        current = None
    if current in MESSAGING_STATUSES:
        buttons.append(
            [
                {
                    "text": "Send Message" if lang == "en" else "Написать",
                    "callback_data": f"deal_msg:{deal.id}",
                }
            ]
        )

    # Add "View Deal" web_app button
    if settings.mini_app_url:
        view_label = "View Deal" if lang == "en" else "Открыть сделку"
        buttons.append(
            [
                {
                    "text": view_label,
                    "web_app": {"url": f"{settings.mini_app_url}/deals/{deal.id}"},
                }
            ]
        )

    if not buttons:
        return None
    return {"inline_keyboard": buttons}


async def notify_deal_status_change(deal) -> None:
    """Notify both parties about a deal status change. Fire-and-forget."""
    try:
        advertiser = deal.advertiser
        owner = deal.owner
        deal_status = deal.status

        for user, actor in [(advertiser, "advertiser"), (owner, "owner")]:
            if user is None:
                continue
            lang = _get_locale(user)
            templates = _STATUS_TEMPLATES.get(lang, _STATUS_TEMPLATES["en"])
            template = templates.get(deal_status)
            if not template:
                continue
            text = template.format(
                deal_id=deal.id,
                price=f"{deal.price:.2f}",
                currency=deal.currency,
            )
            keyboard = _build_deal_keyboard(deal, actor, lang)
            await _send_telegram_message(user.telegram_id, text, reply_markup=keyboard)

        # Notify team members based on status-specific permissions
        try:
            perms = _STATUS_TEAM_PERMISSIONS.get(deal_status)
            if not perms:
                return
            team = await _get_team_recipients(deal, permissions=perms)
            for member in team:
                lang = _get_locale(member.user)
                templates = _STATUS_TEMPLATES.get(lang, _STATUS_TEMPLATES["en"])
                template = templates.get(deal_status)
                if not template:
                    continue
                text = template.format(
                    deal_id=deal.id,
                    price=f"{deal.price:.2f}",
                    currency=deal.currency,
                )
                keyboard = _build_deal_keyboard(deal, "owner", lang)
                await _send_telegram_message(
                    member.user.telegram_id, text, reply_markup=keyboard
                )
        except Exception:
            logger.exception("Failed to send team notification for deal %s", deal.id)
    except Exception:
        logger.exception("Failed to send deal status notification for deal %s", deal.id)


_DEAL_PROPOSAL_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: new deal proposal from the channel owner!\n\n"
        "Price: {price} {currency}\n"
        "{brief_line}"
        "Accept or cancel the proposal."
    ),
    "ru": (
        "Сделка #{deal_id}: новое предложение сделки от владельца канала!\n\n"
        "Цена: {price} {currency}\n"
        "{brief_line}"
        "Примите или отмените предложение."
    ),
}


async def notify_deal_proposal(deal) -> None:
    """Notify the advertiser about a new deal proposal from the channel owner."""
    try:
        advertiser = deal.advertiser
        if advertiser is None:
            return
        lang = _get_locale(advertiser)
        template = _DEAL_PROPOSAL_TEMPLATE.get(lang, _DEAL_PROPOSAL_TEMPLATE["en"])
        brief_line = ""
        if deal.brief:
            label = "Brief" if lang == "en" else "Описание"
            brief_line = f"{label}: {deal.brief[:200]}\n"
        text = template.format(
            deal_id=deal.id,
            price=f"{deal.price:.2f}",
            currency=deal.currency,
            brief_line=brief_line,
        )
        keyboard = _build_deal_keyboard(deal, "advertiser", lang)
        await _send_telegram_message(
            advertiser.telegram_id, text, reply_markup=keyboard
        )
    except Exception:
        logger.exception(
            "Failed to send deal proposal notification for deal %s", deal.id
        )


_AMENDMENT_PROPOSED_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: the channel owner proposed changes:\n"
        "{changes}\n"
        "Accept or reject the proposal."
    ),
    "ru": (
        "Сделка #{deal_id}: владелец канала предложил изменения:\n"
        "{changes}\n"
        "Примите или отклоните предложение."
    ),
}

_AMENDMENT_RESOLVED_TEMPLATE = {
    "en": {
        "accepted": "Deal #{deal_id}: the advertiser accepted your proposed changes.",
        "rejected": "Deal #{deal_id}: the advertiser rejected your proposed changes.",
    },
    "ru": {
        "accepted": "Сделка #{deal_id}: рекламодатель принял ваши предложенные изменения.",
        "rejected": "Сделка #{deal_id}: рекламодатель отклонил ваши предложенные изменения.",
    },
}


def _format_amendment_changes(amendment, lang: str) -> str:
    """Format amendment changes into a readable string."""
    lines = []
    if amendment.proposed_price is not None:
        label = "Price" if lang == "en" else "Цена"
        lines.append(f"  {label}: {amendment.proposed_price:.2f}")
    if amendment.proposed_publish_date is not None:
        label = "Publish date" if lang == "en" else "Дата публикации"
        lines.append(
            f"  {label}: {amendment.proposed_publish_date.strftime('%Y-%m-%d')}"
        )
    return "\n".join(lines) if lines else "—"


async def notify_amendment_proposed(deal, amendment) -> None:
    """Notify the advertiser about a proposed amendment."""
    try:
        advertiser = deal.advertiser
        if advertiser is None:
            return
        lang = _get_locale(advertiser)
        changes = _format_amendment_changes(amendment, lang)
        template = _AMENDMENT_PROPOSED_TEMPLATE.get(
            lang, _AMENDMENT_PROPOSED_TEMPLATE["en"]
        )
        text = template.format(deal_id=deal.id, changes=changes)

        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "Accept" if lang == "en" else "Принять",
                        "callback_data": f"accept_amend:{deal.id}:{amendment.id}",
                    },
                    {
                        "text": "Reject" if lang == "en" else "Отклонить",
                        "callback_data": f"reject_amend:{deal.id}:{amendment.id}",
                    },
                ],
            ]
        }
        await _send_telegram_message(
            advertiser.telegram_id, text, reply_markup=keyboard
        )
    except Exception:
        logger.exception(
            "Failed to send amendment proposed notification for deal %s", deal.id
        )


async def notify_amendment_resolved(deal, amendment) -> None:
    """Notify the owner and team about amendment acceptance/rejection."""
    try:
        owner = deal.owner
        if owner is None:
            return
        lang = _get_locale(owner)
        templates = _AMENDMENT_RESOLVED_TEMPLATE.get(
            lang, _AMENDMENT_RESOLVED_TEMPLATE["en"]
        )
        template = templates.get(amendment.status)
        if not template:
            return
        text = template.format(deal_id=deal.id)
        keyboard = _build_deal_keyboard(deal, "owner", lang)
        await _send_telegram_message(owner.telegram_id, text, reply_markup=keyboard)

        # Notify team members with can_accept_deals (amendments affect deal terms)
        try:
            team = await _get_team_recipients(deal, permission="can_accept_deals")
            for member in team:
                m_lang = _get_locale(member.user)
                m_templates = _AMENDMENT_RESOLVED_TEMPLATE.get(
                    m_lang, _AMENDMENT_RESOLVED_TEMPLATE["en"]
                )
                m_template = m_templates.get(amendment.status)
                if not m_template:
                    continue
                m_text = m_template.format(deal_id=deal.id)
                m_keyboard = _build_deal_keyboard(deal, "owner", m_lang)
                await _send_telegram_message(
                    member.user.telegram_id, m_text, reply_markup=m_keyboard
                )
        except Exception:
            logger.exception(
                "Failed to send team amendment notification for deal %s", deal.id
            )
    except Exception:
        logger.exception(
            "Failed to send amendment resolved notification for deal %s", deal.id
        )


_RETENTION_VIOLATION_TEMPLATE = {
    "en": "Deal #{deal_id}: retention check failed — {reason}. Refund has been initiated, processing on-chain transfer...",
    "ru": "Сделка #{deal_id}: проверка удержания не пройдена — {reason}. Возврат средств инициирован, обработка транзакции...",
}

_RETENTION_VIOLATION_REASONS = {
    "en": {
        "Post was deleted during retention period": "post was deleted",
        "Post was edited during retention period": "post was edited",
    },
    "ru": {
        "Post was deleted during retention period": "пост был удалён",
        "Post was edited during retention period": "пост был отредактирован",
    },
}


async def notify_retention_violation(deal, reason: str) -> None:
    """Notify both parties and team about a retention check failure with specific reason."""
    try:
        advertiser = deal.advertiser
        owner = deal.owner

        for user in [advertiser, owner]:
            if user is None:
                continue
            lang = _get_locale(user)
            template = _RETENTION_VIOLATION_TEMPLATE.get(
                lang, _RETENTION_VIOLATION_TEMPLATE["en"]
            )
            reasons = _RETENTION_VIOLATION_REASONS.get(
                lang, _RETENTION_VIOLATION_REASONS["en"]
            )
            localized_reason = reasons.get(reason, reason)
            text = template.format(deal_id=deal.id, reason=localized_reason)
            await _send_telegram_message(user.telegram_id, text)

        # Notify team members with can_post
        try:
            team = await _get_team_recipients(deal, permission="can_post")
            for member in team:
                m_lang = _get_locale(member.user)
                m_template = _RETENTION_VIOLATION_TEMPLATE.get(
                    m_lang, _RETENTION_VIOLATION_TEMPLATE["en"]
                )
                m_reasons = _RETENTION_VIOLATION_REASONS.get(
                    m_lang, _RETENTION_VIOLATION_REASONS["en"]
                )
                m_reason = m_reasons.get(reason, reason)
                m_text = m_template.format(deal_id=deal.id, reason=m_reason)
                await _send_telegram_message(member.user.telegram_id, m_text)
        except Exception:
            logger.exception(
                "Failed to send team retention notification for deal %s", deal.id
            )
    except Exception:
        logger.exception(
            "Failed to send retention violation notification for deal %s", deal.id
        )


_ESCROW_CONFIRMED_TEMPLATE = {
    "en": {
        "refunded": "Deal #{deal_id}: refund completed! {amount} TON returned to your wallet.",
        "released": "Deal #{deal_id}: payment released! {amount} TON sent to channel owner. Deal complete!",
    },
    "ru": {
        "refunded": "Сделка #{deal_id}: возврат выполнен! {amount} TON возвращены на ваш кошелёк.",
        "released": "Сделка #{deal_id}: оплата переведена! {amount} TON отправлены владельцу канала. Сделка завершена!",
    },
}

_ESCROW_OWNER_CONFIRMED_TEMPLATE = {
    "en": {
        "released": "Deal #{deal_id}: payment received! {amount} TON sent to your wallet.",
    },
    "ru": {
        "released": "Сделка #{deal_id}: оплата получена! {amount} TON отправлены на ваш кошелёк.",
    },
}


async def notify_escrow_confirmed(deal, escrow_state: str, amount: float) -> None:
    """Notify parties when escrow operation is confirmed on-chain.

    For refund: notify advertiser that funds are returned.
    For release: notify advertiser (deal complete), owner and team (payment received).
    """
    try:
        advertiser = deal.advertiser
        owner = deal.owner
        amount_str = f"{amount:.2f}"

        # Notify advertiser
        if advertiser:
            lang = _get_locale(advertiser)
            templates = _ESCROW_CONFIRMED_TEMPLATE.get(
                lang, _ESCROW_CONFIRMED_TEMPLATE["en"]
            )
            template = templates.get(escrow_state)
            if template:
                text = template.format(deal_id=deal.id, amount=amount_str)
                await _send_telegram_message(advertiser.telegram_id, text)

        # Notify owner on release
        if escrow_state == "released" and owner:
            lang = _get_locale(owner)
            templates = _ESCROW_OWNER_CONFIRMED_TEMPLATE.get(
                lang, _ESCROW_OWNER_CONFIRMED_TEMPLATE["en"]
            )
            template = templates.get(escrow_state)
            if template:
                text = template.format(deal_id=deal.id, amount=amount_str)
                await _send_telegram_message(owner.telegram_id, text)

        # Notify team members with can_payout on release (payment received)
        if escrow_state == "released":
            try:
                team = await _get_team_recipients(deal, permission="can_payout")
                for member in team:
                    m_lang = _get_locale(member.user)
                    m_templates = _ESCROW_OWNER_CONFIRMED_TEMPLATE.get(
                        m_lang, _ESCROW_OWNER_CONFIRMED_TEMPLATE["en"]
                    )
                    m_template = m_templates.get(escrow_state)
                    if m_template:
                        m_text = m_template.format(deal_id=deal.id, amount=amount_str)
                        await _send_telegram_message(member.user.telegram_id, m_text)
            except Exception:
                logger.exception(
                    "Failed to send team escrow confirmed notification for deal %s",
                    deal.id,
                )
    except Exception:
        logger.exception(
            "Failed to send escrow confirmed notification for deal %s", deal.id
        )


async def notify_deal_message(
    deal,
    sender,
    recipient_id: int,
    text: str,
    media_items: list[dict] | None = None,
) -> None:
    """Notify the other party about a new deal message. Fire-and-forget."""
    try:
        # We need the recipient's telegram_id; load from the deal relationships
        if recipient_id == deal.advertiser_id:
            recipient = deal.advertiser
        else:
            recipient = deal.owner

        if recipient is None:
            return

        sender_name = sender.first_name or sender.username or "User"
        actor = "advertiser" if recipient_id == deal.advertiser_id else "owner"
        lang = _get_locale(recipient)
        templates = _MESSAGE_TEMPLATE.get(lang, _MESSAGE_TEMPLATE["en"])
        msg = templates.format(
            deal_id=deal.id,
            sender_name=sender_name,
            text=text[:200],
        )
        keyboard = _build_deal_keyboard(deal, actor, lang)
        items = media_items or []
        if len(items) == 1:
            # Single media: send with caption + keyboard
            await _send_telegram_media(
                recipient.telegram_id,
                items[0]["file_id"],
                items[0]["type"],
                caption=msg,
                reply_markup=keyboard,
            )
        elif len(items) >= 2:
            # Album: sendMediaGroup (no reply_markup support) with caption,
            # then a follow-up message with keyboard
            await _send_telegram_media_group(
                recipient.telegram_id,
                items,
                caption=msg,
            )
            if keyboard:
                prompt = (
                    "Choose next action:"
                    if lang == "en"
                    else "Выберите следующее действие:"
                )
                await _send_telegram_message(
                    recipient.telegram_id, prompt, reply_markup=keyboard
                )
        else:
            # Text only
            await _send_telegram_message(
                recipient.telegram_id, msg, reply_markup=keyboard
            )

        # Notify team members based on status-specific permissions
        try:
            perms = _STATUS_TEAM_PERMISSIONS.get(deal.status)
            if perms:
                team = await _get_team_recipients(deal, permissions=perms)
                for member in team:
                    if member.user_id == sender.id:
                        continue  # Don't notify the sender
                    m_lang = _get_locale(member.user)
                    m_templates = _MESSAGE_TEMPLATE.get(m_lang, _MESSAGE_TEMPLATE["en"])
                    m_msg = m_templates.format(
                        deal_id=deal.id,
                        sender_name=sender_name,
                        text=text[:200],
                    )
                    m_keyboard = _build_deal_keyboard(deal, "owner", m_lang)
                    await _send_telegram_message(
                        member.user.telegram_id, m_msg, reply_markup=m_keyboard
                    )
        except Exception:
            logger.exception(
                "Failed to send team message notification for deal %s", deal.id
            )
    except Exception:
        logger.exception(
            "Failed to send deal message notification for deal %s", deal.id
        )


_WALLET_NEEDED_TEMPLATE = {
    "en": {
        "advertiser": (
            "Deal #{deal_id}: please connect your TON wallet to proceed.\n\n"
            "The deal is ready for escrow, but your wallet address is needed.\n"
            "Go to Profile \u2192 Connect Wallet in the Mini App."
        ),
        "owner": (
            "Deal #{deal_id}: please set your payout wallet to receive payment.\n\n"
            "The deal is ready for escrow, but your wallet address is needed.\n"
            "Go to Profile \u2192 Connect Wallet in the Mini App."
        ),
    },
    "ru": {
        "advertiser": (
            "Сделка #{deal_id}: подключите TON-кошелёк для продолжения.\n\n"
            "Сделка готова к эскроу, но необходим адрес вашего кошелька.\n"
            "Перейдите в Профиль \u2192 Подключить кошелёк в Mini App."
        ),
        "owner": (
            "Сделка #{deal_id}: укажите кошелёк для получения оплаты.\n\n"
            "Сделка готова к эскроу, но необходим адрес вашего кошелька.\n"
            "Перейдите в Профиль \u2192 Подключить кошелёк в Mini App."
        ),
    },
}


async def notify_wallet_needed(deal, target_role: str) -> None:
    """Notify a party that their wallet is needed for escrow creation."""
    try:
        user = deal.advertiser if target_role == "advertiser" else deal.owner
        if user is None:
            return
        lang = _get_locale(user)
        templates = _WALLET_NEEDED_TEMPLATE.get(lang, _WALLET_NEEDED_TEMPLATE["en"])
        template = templates.get(target_role, "")
        if not template:
            return
        text = template.format(deal_id=deal.id)
        buttons = []
        if settings.mini_app_url:
            wallet_label = "Connect Wallet" if lang == "en" else "Подключить кошелёк"
            buttons.append(
                [
                    {
                        "text": wallet_label,
                        "web_app": {"url": f"{settings.mini_app_url}/profile"},
                    }
                ]
            )
            view_label = "View Deal" if lang == "en" else "Открыть сделку"
            buttons.append(
                [
                    {
                        "text": view_label,
                        "web_app": {"url": f"{settings.mini_app_url}/deals/{deal.id}"},
                    }
                ]
            )
        keyboard = {"inline_keyboard": buttons} if buttons else None
        await _send_telegram_message(user.telegram_id, text, reply_markup=keyboard)

        # Notify team members with can_payout when owner's wallet is needed
        if target_role == "owner":
            try:
                team = await _get_team_recipients(deal, permission="can_payout")
                for member in team:
                    m_lang = _get_locale(member.user)
                    m_templates = _WALLET_NEEDED_TEMPLATE.get(
                        m_lang, _WALLET_NEEDED_TEMPLATE["en"]
                    )
                    m_template = m_templates.get("owner", "")
                    if not m_template:
                        continue
                    m_text = m_template.format(deal_id=deal.id)
                    await _send_telegram_message(
                        member.user.telegram_id, m_text, reply_markup=keyboard
                    )
            except Exception:
                logger.exception(
                    "Failed to send team wallet notification for deal %s", deal.id
                )
    except Exception:
        logger.exception(
            "Failed to send wallet needed notification for deal %s", deal.id
        )


_ESCROW_PENDING_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: deal accepted! Waiting for the channel owner to confirm "
        "the payment method. You will be notified when it's ready for payment."
    ),
    "ru": (
        "Сделка #{deal_id}: сделка принята! Ожидаем подтверждение способа оплаты "
        "от владельца канала. Вы получите уведомление, когда всё будет готово к оплате."
    ),
}


async def notify_escrow_pending(deal) -> None:
    """Notify advertiser that the deal was accepted and escrow setup is in progress."""
    try:
        advertiser = deal.advertiser
        if advertiser is None:
            return
        lang = _get_locale(advertiser)
        template = _ESCROW_PENDING_TEMPLATE.get(lang, _ESCROW_PENDING_TEMPLATE["en"])
        text = template.format(deal_id=deal.id)
        keyboard = _build_deal_keyboard(deal, "advertiser", lang)
        await _send_telegram_message(advertiser.telegram_id, text, reply_markup=keyboard)
    except Exception:
        logger.exception(
            "Failed to send escrow pending notification for deal %s", deal.id
        )


_ESCROW_AUTO_CREATED_ADVERTISER_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: escrow contract has been created automatically!\n\n"
        "Amount: {price} {currency}\n"
        f"Please deposit within {settings.deal_expire_hours} hours or the deal will expire."
    ),
    "ru": (
        "Сделка #{deal_id}: контракт эскроу создан автоматически!\n\n"
        "Сумма: {price} {currency}\n"
        f"Внесите депозит в течение {settings.deal_expire_hours} ч. или сделка истечёт."
    ),
}

_ESCROW_AUTO_CREATED_OWNER_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: escrow contract has been created automatically!\n\n"
        "Amount: {price} {currency}\n"
        f"Waiting for the advertiser to deposit within {settings.deal_expire_hours} hours."
    ),
    "ru": (
        "Сделка #{deal_id}: контракт эскроу создан автоматически!\n\n"
        "Сумма: {price} {currency}\n"
        f"Ожидаем депозит от рекламодателя в течение {settings.deal_expire_hours} ч."
    ),
}


async def notify_escrow_auto_created(deal) -> None:
    """Notify both parties and team that escrow was auto-created."""
    try:
        for user, actor in [(deal.advertiser, "advertiser"), (deal.owner, "owner")]:
            if user is None:
                continue
            lang = _get_locale(user)
            templates = (
                _ESCROW_AUTO_CREATED_ADVERTISER_TEMPLATE
                if actor == "advertiser"
                else _ESCROW_AUTO_CREATED_OWNER_TEMPLATE
            )
            template = templates.get(lang, templates["en"])
            text = template.format(
                deal_id=deal.id,
                price=f"{deal.price:.2f}",
                currency=deal.currency,
            )
            keyboard = _build_deal_keyboard(deal, actor, lang)
            await _send_telegram_message(user.telegram_id, text, reply_markup=keyboard)

        # Notify team members with can_payout (owner-side)
        try:
            team = await _get_team_recipients(deal, permission="can_payout")
            for member in team:
                m_lang = _get_locale(member.user)
                m_template = _ESCROW_AUTO_CREATED_OWNER_TEMPLATE.get(
                    m_lang, _ESCROW_AUTO_CREATED_OWNER_TEMPLATE["en"]
                )
                m_text = m_template.format(
                    deal_id=deal.id,
                    price=f"{deal.price:.2f}",
                    currency=deal.currency,
                )
                m_keyboard = _build_deal_keyboard(deal, "owner", m_lang)
                await _send_telegram_message(
                    member.user.telegram_id, m_text, reply_markup=m_keyboard
                )
        except Exception:
            logger.exception(
                "Failed to send team escrow notification for deal %s", deal.id
            )
    except Exception:
        logger.exception(
            "Failed to send escrow auto-created notification for deal %s", deal.id
        )


_CREATIVE_SUBMITTED_TEMPLATE = {
    "en": "Deal #{deal_id}: creative submitted (v{version}). Please review:",
    "ru": "Сделка #{deal_id}: креатив отправлен (v{version}). Ознакомьтесь:",
}


async def notify_creative_submitted(deal, creative) -> None:
    """Send the creative content to the advertiser for review."""
    try:
        advertiser = deal.advertiser
        if advertiser is None:
            return
        lang = _get_locale(advertiser)
        template = _CREATIVE_SUBMITTED_TEMPLATE.get(
            lang, _CREATIVE_SUBMITTED_TEMPLATE["en"]
        )
        header = template.format(deal_id=deal.id, version=creative.version)
        keyboard = _build_deal_keyboard(deal, "advertiser", lang)

        items = creative.media_items or []
        if len(items) == 1:
            caption = f"{header}\n\n{creative.text[:900]}" if creative.text else header
            await _send_telegram_media(
                advertiser.telegram_id,
                items[0]["file_id"],
                items[0]["type"],
                caption=caption,
                reply_markup=keyboard,
            )
        elif len(items) >= 2:
            caption = f"{header}\n\n{creative.text[:900]}" if creative.text else header
            await _send_telegram_media_group(
                advertiser.telegram_id,
                items,
                caption=caption,
            )
            if keyboard:
                prompt = (
                    "Choose next action:"
                    if lang == "en"
                    else "Выберите следующее действие:"
                )
                await _send_telegram_message(
                    advertiser.telegram_id, prompt, reply_markup=keyboard
                )
        else:
            text = f"{header}\n\n{creative.text[:1500]}" if creative.text else header
            await _send_telegram_message(
                advertiser.telegram_id, text, reply_markup=keyboard
            )
    except Exception:
        logger.exception(
            "Failed to send creative submitted notification for deal %s", deal.id
        )


_CREATIVE_CHANGES_TEMPLATE = {
    "en": "Deal #{deal_id}: advertiser requested changes to the creative:\n\n{feedback}",
    "ru": "Сделка #{deal_id}: рекламодатель запросил изменения в креативе:\n\n{feedback}",
}


async def notify_creative_changes_requested(deal, creative) -> None:
    """Send the change-request feedback to the channel owner and team."""
    try:
        owner = deal.owner
        if owner is None:
            return
        lang = _get_locale(owner)
        template = _CREATIVE_CHANGES_TEMPLATE.get(
            lang, _CREATIVE_CHANGES_TEMPLATE["en"]
        )
        text = template.format(deal_id=deal.id, feedback=creative.feedback[:1500])
        keyboard = _build_deal_keyboard(deal, "owner", lang)
        await _send_telegram_message(owner.telegram_id, text, reply_markup=keyboard)

        # Notify team members with can_post permission
        try:
            team = await _get_team_recipients(deal, permission="can_post")
            for member in team:
                lang = _get_locale(member.user)
                template = _CREATIVE_CHANGES_TEMPLATE.get(
                    lang, _CREATIVE_CHANGES_TEMPLATE["en"]
                )
                text = template.format(
                    deal_id=deal.id, feedback=creative.feedback[:1500]
                )
                keyboard = _build_deal_keyboard(deal, "owner", lang)
                await _send_telegram_message(
                    member.user.telegram_id, text, reply_markup=keyboard
                )
        except Exception:
            logger.exception(
                "Failed to send team creative changes notification for deal %s", deal.id
            )
    except Exception:
        logger.exception(
            "Failed to send creative changes notification for deal %s", deal.id
        )


_WALLET_CONFIRM_TEMPLATE = {
    "en": (
        "Deal #{deal_id}: please confirm your payout wallet.\n\n"
        "Your profile wallet will be used by default, but you need to "
        "confirm or set a different payout address for this deal.\n"
        "Open the deal in the Mini App to confirm."
    ),
    "ru": (
        "Сделка #{deal_id}: подтвердите кошелёк для выплаты.\n\n"
        "Кошелёк из профиля будет использован по умолчанию, но вам нужно "
        "подтвердить или указать другой адрес для выплаты по этой сделке.\n"
        "Откройте сделку в Mini App для подтверждения."
    ),
}


async def notify_wallet_confirmation_needed(deal) -> None:
    """Notify owner and team that payout wallet confirmation is needed for this deal."""
    try:
        owner = deal.owner
        if owner is None:
            return
        lang = _get_locale(owner)
        template = _WALLET_CONFIRM_TEMPLATE.get(lang, _WALLET_CONFIRM_TEMPLATE["en"])
        text = template.format(deal_id=deal.id)
        buttons = []
        if settings.mini_app_url:
            confirm_label = "Confirm Wallet" if lang == "en" else "Подтвердить кошелёк"
            buttons.append(
                [
                    {
                        "text": confirm_label,
                        "web_app": {"url": f"{settings.mini_app_url}/deals/{deal.id}"},
                    }
                ]
            )
        keyboard = {"inline_keyboard": buttons} if buttons else None
        await _send_telegram_message(owner.telegram_id, text, reply_markup=keyboard)

        # Notify team members with can_payout
        try:
            team = await _get_team_recipients(deal, permission="can_payout")
            for member in team:
                m_lang = _get_locale(member.user)
                m_template = _WALLET_CONFIRM_TEMPLATE.get(
                    m_lang, _WALLET_CONFIRM_TEMPLATE["en"]
                )
                m_text = m_template.format(deal_id=deal.id)
                await _send_telegram_message(
                    member.user.telegram_id, m_text, reply_markup=keyboard
                )
        except Exception:
            logger.exception(
                "Failed to send team wallet confirmation notification for deal %s",
                deal.id,
            )
    except Exception:
        logger.exception(
            "Failed to send wallet confirmation notification for deal %s", deal.id
        )
