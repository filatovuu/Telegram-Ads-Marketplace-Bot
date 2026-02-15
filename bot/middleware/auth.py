import logging
from typing import Any, Awaitable, Callable, Dict

import httpx
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_tg_user(event: TelegramObject) -> TgUser | None:
    """Extract the Telegram user from any event type."""
    if hasattr(event, "from_user") and event.from_user:
        return event.from_user
    if hasattr(event, "message") and event.message and event.message.from_user:
        return event.message.from_user
    return None


class AuthMiddleware(BaseMiddleware):
    """Register or fetch the user in the backend on every update.

    Injects data["db_user"] with the backend user dict for downstream handlers.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = _extract_tg_user(event)
        if tg_user is None:
            return await handler(event, data)

        try:
            async with httpx.AsyncClient(
                base_url=settings.backend_url, timeout=5.0
            ) as client:
                resp = await client.post(
                    "/api/internal/bot/upsert-user",
                    json={
                        "telegram_id": tg_user.id,
                        "username": tg_user.username,
                        "first_name": tg_user.first_name,
                        "last_name": tg_user.last_name,
                        "language_code": tg_user.language_code,
                    },
                )
                if resp.status_code == 200:
                    data["db_user"] = resp.json()
                else:
                    logger.warning("Bot auth upsert failed: %s", resp.status_code)
                    data["db_user"] = None
        except Exception:
            logger.exception("Bot auth middleware error")
            data["db_user"] = None

        return await handler(event, data)
