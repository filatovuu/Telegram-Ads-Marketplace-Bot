"""Bot handlers for deal actions, messaging, creative submission, brief filling, amendments, creative review, and scheduling via inline buttons + FSM."""

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    WebAppInfo,
)

from app.config import settings
from services import backend
from states.deal import (
    AmendmentProposalFSM,
    CreativeReviewFSM,
    CreativeSubmitFSM,
    DealBriefFSM,
    DealMessageFSM,
    SchedulePostFSM,
)
from templates.messages import MESSAGES

router = Router(name="deals")
logger = logging.getLogger(__name__)


async def _safe_answer(callback: CallbackQuery, text: str, **kwargs) -> None:
    """Answer a callback query safely, handling inaccessible messages."""
    if isinstance(callback.message, InaccessibleMessage) or callback.message is None:
        await callback.answer(text[:200], show_alert=True)
    else:
        await callback.message.answer(text, **kwargs)
        await callback.answer()


async def _safe_remove_keyboard(callback: CallbackQuery) -> None:
    """Remove inline keyboard from the callback message, ignoring errors."""
    if isinstance(callback.message, InaccessibleMessage) or callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

# Actions that require creative text input instead of direct transition
_CREATIVE_ACTIONS = {"submit_creative"}

# Actions that require scheduling input instead of direct transition
_SCHEDULE_ACTIONS = {"schedule"}

# Actions that require feedback input instead of direct transition
_FEEDBACK_ACTIONS = {"request_changes"}

# Actions that can only be performed in the Mini App (require wallet addresses, etc.)
_MINI_APP_ONLY_ACTIONS: set[str] = set()

# Human-readable action labels for inline buttons (bot-side)
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


def _lang(locale: str) -> str:
    return locale if locale in MESSAGES else "en"


def _build_actions_keyboard(
    deal_id: int, available_actions: list[str], lang: str,
    deal_status: str | None = None, actor: str | None = None,
) -> InlineKeyboardMarkup | None:
    """Build inline keyboard from available_actions list."""
    labels = _ACTION_LABELS.get(lang, _ACTION_LABELS["en"])
    buttons: list[list[InlineKeyboardButton]] = []

    for action in available_actions:
        # Skip actions that require Mini App (wallet addresses, etc.)
        if action in _MINI_APP_ONLY_ACTIONS:
            continue
        label = labels.get(action, action)
        cb_data = f"deal:{deal_id}:{action}"
        if len(cb_data) > 64:
            continue
        buttons.append([InlineKeyboardButton(text=label, callback_data=cb_data)])

    # Add "Propose Changes" for owner in NEGOTIATION
    if actor == "owner" and deal_status == "NEGOTIATION":
        propose_label = "Propose Changes" if lang == "en" else "Предложить изменения"
        buttons.append([InlineKeyboardButton(text=propose_label, callback_data=f"amend_propose:{deal_id}")])

    # Always add a "Send Message" button
    msg_label = "Send Message" if lang == "en" else "Написать"
    buttons.append([InlineKeyboardButton(text=msg_label, callback_data=f"deal_msg:{deal_id}")])

    # Add "View Deal" web_app button to open Mini App on the deal page
    if settings.mini_app_url:
        view_label = "View Deal" if lang == "en" else "Открыть сделку"
        buttons.append([InlineKeyboardButton(
            text=view_label,
            web_app=WebAppInfo(url=f"{settings.mini_app_url}/deals/{deal_id}"),
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


async def _fetch_deal_keyboard(
    deal_id: int, user_id: int, lang: str,
) -> InlineKeyboardMarkup | None:
    """Fetch deal detail and build an inline keyboard with available actions."""
    detail = await backend.get_deal_detail(deal_id, user_id)
    if not detail or not detail.get("available_actions"):
        return None
    actor = "owner" if detail.get("owner_id") == user_id else "advertiser"
    return _build_actions_keyboard(
        deal_id, detail["available_actions"], lang,
        deal_status=detail.get("status"), actor=actor,
    )


async def _resolve_user(callback: CallbackQuery, lang: str, internal_user_id: int | None) -> int | None:
    """Resolve internal user ID, upserting if needed."""
    if internal_user_id is not None:
        return internal_user_id
    user = await backend.upsert_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name,
    )
    if user:
        return user["id"]
    return None


# ---------------------------------------------------------------------------
# Deal action callback (state machine transitions)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("deal:"))
async def cb_deal_action(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """Handle deal:{id}:{action} callbacks — trigger state machine transition."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return

    deal_id_str, action = parts[1], parts[2]
    try:
        deal_id = int(deal_id_str)
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["deal_transition_error"])
        await _safe_remove_keyboard(callback)
        return

    # Clear any active FSM state (user chose an action instead of typing)
    await state.clear()

    # Special case: actions that require Mini App (wallet, escrow)
    if action in _MINI_APP_ONLY_ACTIONS:
        await _safe_answer(callback, MESSAGES[lang]["escrow_use_mini_app"])
        await _safe_remove_keyboard(callback)
        return

    # Special case: creative submission needs text input
    if action in _CREATIVE_ACTIONS:
        await state.set_state(CreativeSubmitFSM.waiting_for_post)
        await state.update_data(deal_id=deal_id, user_id=uid)
        await _safe_answer(callback, MESSAGES[lang]["creative_prompt"])
        await _safe_remove_keyboard(callback)
        return

    # Special case: request_changes needs feedback input
    if action in _FEEDBACK_ACTIONS:
        await state.set_state(CreativeReviewFSM.waiting_for_feedback)
        await state.update_data(deal_id=deal_id, user_id=uid)
        await _safe_answer(callback, MESSAGES[lang]["creative_feedback_prompt"])
        await _safe_remove_keyboard(callback)
        return

    # Special case: schedule needs datetime input
    if action in _SCHEDULE_ACTIONS:
        await state.set_state(SchedulePostFSM.waiting_for_datetime)
        await state.update_data(deal_id=deal_id, user_id=uid)
        await _safe_answer(callback, MESSAGES[lang]["schedule_prompt"])
        await _safe_remove_keyboard(callback)
        return

    # Special case: approve_creative calls dedicated endpoint
    if action == "approve_creative":
        result = await backend.approve_creative(deal_id, uid)
        if result:
            keyboard = await _fetch_deal_keyboard(deal_id, uid, lang)
            await _safe_answer(callback, MESSAGES[lang]["creative_approved"].format(deal_id=deal_id), reply_markup=keyboard)
        else:
            await _safe_answer(callback, MESSAGES[lang]["creative_approve_error"])
        await _safe_remove_keyboard(callback)
        return

    # Special case: "send" action — if deal has no brief, enter brief FSM
    if action == "send":
        detail = await backend.get_deal_detail(deal_id, uid)
        if detail and not detail.get("brief"):
            await state.set_state(DealBriefFSM.waiting_for_brief)
            await state.update_data(deal_id=deal_id, user_id=uid)
            await _safe_answer(callback, MESSAGES[lang]["deal_brief_prompt"])
            await _safe_remove_keyboard(callback)
            return

    try:
        result = await backend.transition_deal(deal_id, uid, action)
    except ValueError as exc:
        detail = str(exc)
        if "wallet" in detail.lower():
            await _safe_answer(callback, MESSAGES[lang]["wallet_required_deal"])
        else:
            await _safe_answer(callback, detail)
        await _safe_remove_keyboard(callback)
        return

    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, uid, lang)
        await _safe_answer(
            callback,
            MESSAGES[lang]["deal_transition_success"].format(
                deal_id=deal_id, status=result["status"],
            ),
            reply_markup=keyboard,
        )
    else:
        await _safe_answer(callback, MESSAGES[lang]["deal_transition_error"])

    await _safe_remove_keyboard(callback)


# ---------------------------------------------------------------------------
# Deal messaging FSM
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("deal_msg:"))
async def cb_deal_message_start(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """Enter messaging FSM — prompt user to type, show available actions as buttons."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer()
        return

    try:
        deal_id = int(parts[1])
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["deal_msg_error"])
        return

    await state.set_state(DealMessageFSM.waiting_for_text)
    await state.update_data(deal_id=deal_id, user_id=uid)

    # Fetch deal detail to get available actions
    detail = await backend.get_deal_detail(deal_id, uid)
    keyboard = None
    if detail and detail.get("available_actions"):
        actor = "owner" if detail.get("owner_id") == uid else "advertiser"
        keyboard = _build_actions_keyboard(
            deal_id, detail["available_actions"], lang,
            deal_status=detail.get("status"), actor=actor,
        )

    await _safe_answer(
        callback,
        MESSAGES[lang]["deal_msg_prompt"].format(deal_id=deal_id),
        reply_markup=keyboard,
    )


@router.message(DealMessageFSM.waiting_for_text)
async def fsm_deal_message(
    message: Message,
    state: FSMContext,
    locale: str = "en",
    album: list[Message] | None = None,
) -> None:
    """Capture deal message (text, media, album, or both), send via backend."""
    lang = _lang(locale)

    # Collect all messages (album or single)
    messages = album if album else [message]

    # Extract text from the first message
    text = messages[0].text or messages[0].caption or ""

    # Extract media from all messages in the album
    media_items: list[dict] = []
    for msg in messages:
        if msg.photo:
            media_items.append({"file_id": msg.photo[-1].file_id, "type": "photo"})
        elif msg.video:
            media_items.append({"file_id": msg.video.file_id, "type": "video"})
        elif msg.document:
            media_items.append({"file_id": msg.document.file_id, "type": "document"})
        elif msg.animation:
            media_items.append({"file_id": msg.animation.file_id, "type": "animation"})

    if not text and not media_items:
        await message.answer(MESSAGES[lang]["deal_msg_empty"])
        return

    # Ensure text is not empty for the backend (at least a space)
    if not text:
        text = " "

    data = await state.get_data()
    deal_id = data.get("deal_id")
    user_id = data.get("user_id")

    result = await backend.send_deal_message(
        deal_id, user_id, text,
        media_items=media_items if media_items else None,
    )
    if result:
        detail = await backend.get_deal_detail(deal_id, user_id)
        keyboard = None
        if detail and detail.get("available_actions"):
            actor = "owner" if detail.get("owner_id") == user_id else "advertiser"
            keyboard = _build_actions_keyboard(
                deal_id, detail["available_actions"], lang,
                deal_status=detail.get("status"), actor=actor,
            )

        await state.clear()
        await message.answer(
            MESSAGES[lang]["deal_msg_sent"].format(deal_id=deal_id),
            reply_markup=keyboard,
        )
    else:
        await message.answer(MESSAGES[lang]["deal_msg_error"])
        await state.clear()


# ---------------------------------------------------------------------------
# Creative submission FSM (enhanced: text → optional media → confirm)
# ---------------------------------------------------------------------------

@router.message(CreativeSubmitFSM.waiting_for_post)
async def fsm_creative_post(
    message: Message,
    state: FSMContext,
    locale: str = "en",
    album: list[Message] | None = None,
) -> None:
    """Capture creative as a single post or album — then show visual preview.

    Creative backend accepts single media only, so only the first item is
    submitted. All media are shown in the preview for the user.
    """
    lang = _lang(locale)

    # Collect all messages (album or single)
    messages = album if album else [message]

    text = messages[0].text or messages[0].caption or ""

    # Extract media from all messages
    media_items: list[dict] = []
    for msg in messages:
        if msg.photo:
            media_items.append({"file_id": msg.photo[-1].file_id, "type": "photo"})
        elif msg.video:
            media_items.append({"file_id": msg.video.file_id, "type": "video"})
        elif msg.document:
            media_items.append({"file_id": msg.document.file_id, "type": "document"})
        elif msg.animation:
            media_items.append({"file_id": msg.animation.file_id, "type": "animation"})

    if not text and not media_items:
        await message.answer(MESSAGES[lang]["creative_empty"])
        return

    await state.update_data(
        creative_text=text,
        media_items=media_items if media_items else None,
    )
    await state.set_state(CreativeSubmitFSM.confirm_creative)

    # Visual preview — send the creative back exactly as it will look
    text_preview = text[:1024] if text else ""
    if len(media_items) >= 2:
        # Album preview via media group
        input_media = []
        for i, item in enumerate(media_items):
            cap = text_preview if i == 0 and text_preview else None
            if item["type"] == "photo":
                input_media.append(InputMediaPhoto(media=item["file_id"], caption=cap))
            elif item["type"] == "video":
                input_media.append(InputMediaVideo(media=item["file_id"], caption=cap))
        if input_media:
            await message.answer_media_group(input_media)
        elif text_preview:
            await message.answer(text_preview)
    elif media_items:
        item = media_items[0]
        if item["type"] == "photo":
            await message.answer_photo(item["file_id"], caption=text_preview or None)
        elif item["type"] == "video":
            await message.answer_video(item["file_id"], caption=text_preview or None)
        elif item["type"] == "document":
            await message.answer_document(item["file_id"], caption=text_preview or None)
        elif item["type"] == "animation":
            await message.answer_animation(item["file_id"], caption=text_preview or None)
    elif text_preview:
        await message.answer(text_preview)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=MESSAGES[lang]["creative_confirm_btn"], callback_data="creative_fsm_confirm"),
        InlineKeyboardButton(text=MESSAGES[lang]["creative_cancel_btn"], callback_data="creative_fsm_cancel"),
    ]])
    await message.answer(MESSAGES[lang]["creative_confirm"], reply_markup=confirm_kb)


@router.callback_query(CreativeSubmitFSM.confirm_creative, F.data == "creative_fsm_confirm")
async def fsm_creative_confirm_cb(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Submit the creative via backend API (inline button)."""
    lang = _lang(locale)
    data = await state.get_data()
    deal_id = data["deal_id"]
    user_id = data["user_id"]

    result = await backend.submit_creative(
        deal_id, user_id,
        text=data.get("creative_text", ""),
        media_items=data.get("media_items"),
    )
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await _safe_answer(callback, MESSAGES[lang]["creative_submitted"].format(deal_id=deal_id), reply_markup=keyboard)
    else:
        await _safe_answer(callback, MESSAGES[lang]["creative_submit_error"])

    await state.clear()


@router.callback_query(CreativeSubmitFSM.confirm_creative, F.data == "creative_fsm_cancel")
async def fsm_creative_cancel_cb(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Cancel creative submission (inline button)."""
    lang = _lang(locale)
    await state.clear()
    await _safe_answer(callback, MESSAGES[lang]["cancelled"])


@router.message(CreativeSubmitFSM.confirm_creative, Command("confirm"))
async def fsm_creative_confirm(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Submit the creative via backend API (command fallback)."""
    lang = _lang(locale)
    data = await state.get_data()
    deal_id = data["deal_id"]
    user_id = data["user_id"]

    result = await backend.submit_creative(
        deal_id, user_id,
        text=data.get("creative_text", ""),
        media_items=data.get("media_items"),
    )
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await message.answer(MESSAGES[lang]["creative_submitted"].format(deal_id=deal_id), reply_markup=keyboard)
    else:
        await message.answer(MESSAGES[lang]["creative_submit_error"])

    await state.clear()


# ---------------------------------------------------------------------------
# Creative review FSM (advertiser feedback)
# ---------------------------------------------------------------------------

@router.message(CreativeReviewFSM.waiting_for_feedback)
async def fsm_creative_feedback(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Capture feedback text and request changes via backend."""
    lang = _lang(locale)

    if not message.text:
        await message.answer(MESSAGES[lang]["deal_msg_text_only"])
        return

    data = await state.get_data()
    deal_id = data.get("deal_id")
    user_id = data.get("user_id")

    result = await backend.request_creative_changes(deal_id, user_id, message.text)
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await message.answer(MESSAGES[lang]["creative_changes_sent"].format(deal_id=deal_id), reply_markup=keyboard)
    else:
        await message.answer(MESSAGES[lang]["creative_changes_error"])

    await state.clear()


# ---------------------------------------------------------------------------
# Schedule Post FSM
# ---------------------------------------------------------------------------

@router.message(SchedulePostFSM.waiting_for_datetime)
async def fsm_schedule_datetime(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Capture schedule datetime."""
    lang = _lang(locale)

    if not message.text:
        await message.answer(MESSAGES[lang]["schedule_invalid"])
        return

    try:
        parsed = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        await state.update_data(scheduled_at=parsed.isoformat())
    except ValueError:
        await message.answer(MESSAGES[lang]["schedule_invalid"])
        return

    data = await state.get_data()
    await state.set_state(SchedulePostFSM.confirm_schedule)
    await message.answer(MESSAGES[lang]["schedule_confirm"].format(
        datetime=data["scheduled_at"],
    ))


@router.message(SchedulePostFSM.confirm_schedule, Command("confirm"))
async def fsm_schedule_confirm(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Schedule the post via backend API."""
    lang = _lang(locale)
    data = await state.get_data()
    deal_id = data["deal_id"]
    user_id = data["user_id"]

    result = await backend.schedule_post(deal_id, user_id, data["scheduled_at"])
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await message.answer(MESSAGES[lang]["schedule_success"].format(deal_id=deal_id), reply_markup=keyboard)
    else:
        await message.answer(MESSAGES[lang]["schedule_error"])

    await state.clear()


# ---------------------------------------------------------------------------
# Deal Brief FSM — fill brief before sending deal
# ---------------------------------------------------------------------------

@router.message(DealBriefFSM.waiting_for_brief)
async def fsm_brief_text(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Capture brief text."""
    lang = _lang(locale)
    if not message.text:
        await message.answer(MESSAGES[lang]["deal_msg_text_only"])
        return
    await state.update_data(brief=message.text)
    await state.set_state(DealBriefFSM.waiting_for_publish_from)
    await message.answer(MESSAGES[lang]["deal_publish_from_prompt"])


@router.message(DealBriefFSM.waiting_for_publish_from, Command("skip"))
async def fsm_brief_skip_from(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Skip publish_from, ask for publish_to."""
    lang = _lang(locale)
    await state.set_state(DealBriefFSM.waiting_for_publish_to)
    await message.answer(MESSAGES[lang]["deal_publish_to_prompt"])


@router.message(DealBriefFSM.waiting_for_publish_from)
async def fsm_brief_from(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Capture publish_from date."""
    lang = _lang(locale)
    if not message.text:
        await message.answer(MESSAGES[lang]["deal_publish_date_invalid"])
        return
    try:
        parsed = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        await state.update_data(publish_from=parsed.isoformat())
    except ValueError:
        await message.answer(MESSAGES[lang]["deal_publish_date_invalid"])
        return
    await state.set_state(DealBriefFSM.waiting_for_publish_to)
    await message.answer(MESSAGES[lang]["deal_publish_to_prompt"])


@router.message(DealBriefFSM.waiting_for_publish_to, Command("skip"))
async def fsm_brief_skip_to(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Skip publish_to, go to confirm."""
    lang = _lang(locale)
    data = await state.get_data()
    await state.set_state(DealBriefFSM.confirm_and_send)
    await message.answer(MESSAGES[lang]["deal_brief_confirm"].format(
        brief=data.get("brief", "—"),
        publish_from=data.get("publish_from", "—"),
        publish_to=data.get("publish_to", "—"),
    ))


@router.message(DealBriefFSM.waiting_for_publish_to)
async def fsm_brief_to(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Capture publish_to date."""
    lang = _lang(locale)
    if not message.text:
        await message.answer(MESSAGES[lang]["deal_publish_date_invalid"])
        return
    try:
        parsed = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        await state.update_data(publish_to=parsed.isoformat())
    except ValueError:
        await message.answer(MESSAGES[lang]["deal_publish_date_invalid"])
        return
    data = await state.get_data()
    await state.set_state(DealBriefFSM.confirm_and_send)
    await message.answer(MESSAGES[lang]["deal_brief_confirm"].format(
        brief=data.get("brief", "—"),
        publish_from=data.get("publish_from", "—"),
        publish_to=data.get("publish_to", message.text.strip()),
    ))


@router.message(DealBriefFSM.confirm_and_send, Command("confirm"))
async def fsm_brief_confirm(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Save brief and transition deal to send."""
    lang = _lang(locale)
    data = await state.get_data()
    deal_id = data["deal_id"]
    user_id = data["user_id"]

    # Save brief fields
    result = await backend.update_deal_brief(
        deal_id, user_id,
        brief=data.get("brief"),
        publish_from=data.get("publish_from"),
        publish_to=data.get("publish_to"),
    )
    if not result:
        await message.answer(MESSAGES[lang]["deal_brief_save_error"])
        await state.clear()
        return

    # Now trigger the "send" transition
    transition = await backend.transition_deal(deal_id, user_id, "send")
    if transition:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await message.answer(MESSAGES[lang]["deal_brief_saved"], reply_markup=keyboard)
    else:
        await message.answer(MESSAGES[lang]["deal_brief_save_error"])

    await state.clear()


# ---------------------------------------------------------------------------
# Amendment Proposal FSM — owner proposes changes
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("amend_propose:"))
async def cb_amend_propose(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """Owner starts the amendment proposal flow."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer()
        return

    try:
        deal_id = int(parts[1])
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["amendment_error"])
        return

    await state.clear()
    await state.set_state(AmendmentProposalFSM.waiting_for_price)
    await state.update_data(deal_id=deal_id, user_id=uid)
    await _safe_answer(callback, MESSAGES[lang]["amendment_price_prompt"])


@router.message(AmendmentProposalFSM.waiting_for_price, Command("skip"))
async def fsm_amend_skip_price(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    lang = _lang(locale)
    await state.set_state(AmendmentProposalFSM.waiting_for_publish_date)
    await message.answer(MESSAGES[lang]["amendment_publish_date_prompt"])


@router.message(AmendmentProposalFSM.waiting_for_price)
async def fsm_amend_price(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    lang = _lang(locale)
    if not message.text:
        await message.answer(MESSAGES[lang]["amendment_price_prompt"])
        return
    try:
        price = str(float(message.text.strip()))
        await state.update_data(proposed_price=price)
    except ValueError:
        await message.answer(MESSAGES[lang]["amendment_price_prompt"])
        return
    await state.set_state(AmendmentProposalFSM.waiting_for_publish_date)
    await message.answer(MESSAGES[lang]["amendment_publish_date_prompt"])


@router.message(AmendmentProposalFSM.waiting_for_publish_date, Command("skip"))
async def fsm_amend_skip_date(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    lang = _lang(locale)
    data = await state.get_data()
    if not any(data.get(k) for k in ("proposed_price", "proposed_publish_date")):
        await message.answer(MESSAGES[lang]["amendment_nothing"])
        await state.clear()
        return
    await state.set_state(AmendmentProposalFSM.confirm)
    await message.answer(MESSAGES[lang]["amendment_confirm"].format(
        price=data.get("proposed_price", "—"),
        publish_date=data.get("proposed_publish_date", "—"),
    ))


@router.message(AmendmentProposalFSM.waiting_for_publish_date)
async def fsm_amend_date(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    lang = _lang(locale)
    if not message.text:
        await message.answer(MESSAGES[lang]["amendment_publish_date_prompt"])
        return
    try:
        parsed = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        await state.update_data(proposed_publish_date=parsed.isoformat())
    except ValueError:
        await message.answer(MESSAGES[lang]["deal_publish_date_invalid"])
        return
    data = await state.get_data()
    await state.set_state(AmendmentProposalFSM.confirm)
    await message.answer(MESSAGES[lang]["amendment_confirm"].format(
        price=data.get("proposed_price", "—"),
        publish_date=data.get("proposed_publish_date", message.text.strip()),
    ))


@router.message(AmendmentProposalFSM.confirm, Command("confirm"))
async def fsm_amend_confirm(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    lang = _lang(locale)
    data = await state.get_data()
    deal_id = data["deal_id"]
    user_id = data["user_id"]

    result = await backend.propose_amendment(
        deal_id, user_id,
        proposed_price=data.get("proposed_price"),
        proposed_publish_date=data.get("proposed_publish_date"),
    )
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, user_id, lang)
        await message.answer(MESSAGES[lang]["amendment_sent"], reply_markup=keyboard)
    else:
        await message.answer(MESSAGES[lang]["amendment_error"])

    await state.clear()


# ---------------------------------------------------------------------------
# Amendment accept / reject callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("accept_amend:"))
async def cb_accept_amend(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """Advertiser accepts an amendment."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        deal_id = int(parts[1])
        amendment_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["amendment_resolve_error"])
        return

    await state.clear()
    result = await backend.resolve_amendment(deal_id, amendment_id, uid, "accept")
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, uid, lang)
        await _safe_answer(callback, MESSAGES[lang]["amendment_accepted"], reply_markup=keyboard)
    else:
        await _safe_answer(callback, MESSAGES[lang]["amendment_resolve_error"])

    await _safe_remove_keyboard(callback)


@router.callback_query(F.data.startswith("reject_amend:"))
async def cb_reject_amend(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """Advertiser rejects an amendment."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        deal_id = int(parts[1])
        amendment_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["amendment_resolve_error"])
        return

    await state.clear()
    result = await backend.resolve_amendment(deal_id, amendment_id, uid, "reject")
    if result:
        keyboard = await _fetch_deal_keyboard(deal_id, uid, lang)
        await _safe_answer(callback, MESSAGES[lang]["amendment_rejected"], reply_markup=keyboard)
    else:
        await _safe_answer(callback, MESSAGES[lang]["amendment_resolve_error"])

    await _safe_remove_keyboard(callback)


# ---------------------------------------------------------------------------
# Deal view callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("deal_view:"))
async def cb_deal_view(
    callback: CallbackQuery,
    state: FSMContext,
    locale: str = "en",
    internal_user_id: int | None = None,
) -> None:
    """View deal detail in the bot with action buttons."""
    lang = _lang(locale)
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer()
        return

    try:
        deal_id = int(parts[1])
    except ValueError:
        await callback.answer()
        return

    uid = await _resolve_user(callback, lang, internal_user_id)
    if uid is None:
        await _safe_answer(callback, MESSAGES[lang]["deal_not_found"])
        return

    # Clear FSM if user is viewing a deal
    await state.clear()

    detail = await backend.get_deal_detail(deal_id, uid)
    if not detail:
        await _safe_answer(callback, MESSAGES[lang]["deal_not_found"])
        return

    # Build wallet line — each role sees only their own wallet
    wallet_line = ""
    is_owner = detail.get("owner_id") == uid
    if is_owner:
        owner_wallet = detail.get("owner_wallet_address")
        if owner_wallet:
            label = "Payout wallet" if lang == "en" else "Кошелёк для выплаты"
            wallet_line = f"\n{label}: {owner_wallet[:8]}\u2026{owner_wallet[-4:]}"

    # Build escrow line with Tonscan link
    escrow_line = ""
    escrow_data = detail.get("escrow")
    if escrow_data and escrow_data.get("contract_address"):
        contract_addr = escrow_data["contract_address"]
        if not contract_addr.startswith("pending-"):
            from app.config import settings as bot_settings

            base = (
                "https://tonscan.org/address/"
                if bot_settings.ton_network == "mainnet"
                else "https://testnet.tonscan.org/address/"
            )
            label = "Contract" if lang == "en" else "Контракт"
            short_addr = f"{contract_addr[:8]}\u2026{contract_addr[-4:]}"
            escrow_line = f'\n{label}: <a href="{base}{contract_addr}">{short_addr}</a>'

    text = MESSAGES[lang]["deal_detail_bot"].format(
        deal_id=detail["id"],
        status=detail["status"],
        price=detail["price"],
        currency=detail["currency"],
        wallet_line=wallet_line,
        escrow_line=escrow_line,
    )

    keyboard = None
    if detail.get("available_actions"):
        actor = "owner" if detail.get("owner_id") == uid else "advertiser"
        keyboard = _build_actions_keyboard(
            deal_id, detail["available_actions"], lang,
            deal_status=detail.get("status"), actor=actor,
        )

    await _safe_answer(callback, text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Cancel command
# ---------------------------------------------------------------------------

@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    locale: str = "en",
) -> None:
    """Cancel any active FSM state."""
    lang = _lang(locale)
    current = await state.get_state()
    if current is None:
        await message.answer(MESSAGES[lang]["nothing_to_cancel"])
        return
    await state.clear()
    await message.answer(MESSAGES[lang]["cancelled"])
