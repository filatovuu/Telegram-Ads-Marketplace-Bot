from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser


class I18nMiddleware(BaseMiddleware):
    """Determine the user locale and inject it into handler data.

    Priority:
    1. Locale from backend user profile (db_user)
    2. Telegram language_code
    3. Default to "en"
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        locale = "en"

        # Try backend user profile first
        db_user = data.get("db_user")
        if db_user and isinstance(db_user, dict):
            locale = db_user.get("locale", "en")
        else:
            # Fallback to Telegram language_code
            tg_user: TgUser | None = getattr(event, "from_user", None)
            if tg_user and tg_user.language_code:
                locale = tg_user.language_code if tg_user.language_code in ("en", "ru") else "en"

        data["locale"] = locale
        return await handler(event, data)
