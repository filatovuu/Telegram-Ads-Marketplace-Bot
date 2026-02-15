import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.config import settings
from services import backend
from templates.messages import MESSAGES

router = Router(name="callbacks")
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {
    "NEGOTIATION", "OWNER_ACCEPTED", "AWAITING_ESCROW_PAYMENT", "ESCROW_FUNDED",
    "CREATIVE_PENDING_OWNER", "CREATIVE_SUBMITTED", "CREATIVE_CHANGES_REQUESTED",
    "CREATIVE_APPROVED",
}


async def _send_help(target: Message, locale: str) -> None:
    lang = locale if locale in MESSAGES else "en"
    await target.answer(MESSAGES[lang]["help"])


async def _send_deals(target: Message, user_tg_id: int, username: str | None,
                      first_name: str | None, last_name: str | None,
                      locale: str) -> None:
    lang = locale if locale in MESSAGES else "en"
    msg = MESSAGES[lang]

    try:
        user = await backend.upsert_user(user_tg_id, username, first_name, last_name)
        if not user:
            await target.answer(msg["no_deals"])
            return

        all_deals = await backend.get_user_deals(user["id"])

        if not all_deals:
            await target.answer(msg["no_deals"])
            return

        active_deals = [d for d in all_deals if d["status"] in ACTIVE_STATUSES]

        # Count other categories
        cat_counts: dict[str, int] = {}
        cat_keys = {
            "SCHEDULED": "deals_cat_scheduled",
            "POSTED": "deals_cat_published",
            "RETENTION_CHECK": "deals_cat_published",
            "RELEASED": "deals_cat_completed",
            "DRAFT": "deals_cat_drafts",
            "CANCELLED": "deals_cat_cancelled",
            "EXPIRED": "deals_cat_cancelled",
            "REFUNDED": "deals_cat_cancelled",
        }
        for deal in all_deals:
            key = cat_keys.get(deal["status"])
            if key:
                cat_counts[key] = cat_counts.get(key, 0) + 1

        # Build summary line
        summary_parts = []
        for key in ("deals_cat_scheduled", "deals_cat_published", "deals_cat_completed",
                     "deals_cat_drafts", "deals_cat_cancelled"):
            count = cat_counts.get(key, 0)
            if count > 0:
                summary_parts.append(msg[key].format(count=count))
        summary_line = msg["deals_also"].format(categories=", ".join(summary_parts)) if summary_parts else ""

        lines: list[str] = []
        buttons: list[list[InlineKeyboardButton]] = []

        if active_deals:
            lines.append(msg["deals_active_header"])
            for deal in active_deals[:10]:
                lines.append(
                    msg["deals_list_item"].format(
                        deal_id=deal["id"],
                        status=deal["status"],
                        price=deal["price"],
                        currency=deal["currency"],
                    )
                )
                buttons.append([
                    InlineKeyboardButton(
                        text=f"#{deal['id']} — {deal['status']}",
                        callback_data=f"deal_view:{deal['id']}",
                    ),
                ])
            if summary_line:
                lines.append("")
                lines.append(summary_line)
        else:
            lines.append(msg["no_active_deals"])
            if summary_line:
                lines.append(summary_line)

        # Add "View All Deals" Mini App button
        if settings.mini_app_url:
            buttons.append([
                InlineKeyboardButton(
                    text=msg["deals_view_all_app"],
                    web_app=WebAppInfo(url=f"{settings.mini_app_url}/deals"),
                ),
            ])

        markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        await target.answer("\n".join(lines), reply_markup=markup)
    except Exception:
        logger.exception("Failed to fetch deals for user %d", user_tg_id)
        await target.answer(msg["no_deals"])


# ── Command handlers ────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message, locale: str = "en") -> None:
    await _send_help(message, locale)


@router.message(Command("deals"))
async def cmd_deals(message: Message, locale: str = "en") -> None:
    await _send_deals(
        message, message.from_user.id, message.from_user.username,
        message.from_user.first_name, message.from_user.last_name, locale,
    )


# ── Callback handlers ───────────────────────────────────────────

@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, locale: str = "en") -> None:
    await _send_help(callback.message, locale)
    await callback.answer()


@router.callback_query(F.data == "my_deals")
async def cb_my_deals(callback: CallbackQuery, locale: str = "en") -> None:
    await _send_deals(
        callback.message, callback.from_user.id, callback.from_user.username,
        callback.from_user.first_name, callback.from_user.last_name, locale,
    )
    await callback.answer()
