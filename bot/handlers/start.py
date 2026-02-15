from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.config import settings
from templates.messages import MESSAGES

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, locale: str = "en") -> None:
    """Handle /start command. Send welcome message with inline keyboard."""
    lang = locale if locale in MESSAGES else "en"
    msgs = MESSAGES[lang]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=msgs["btn_open_app"],
                    web_app=WebAppInfo(url=settings.mini_app_url),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_my_deals"],
                    callback_data="my_deals",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=msgs["btn_help"],
                    callback_data="help",
                ),
            ],
        ]
    )

    await message.answer(text=msgs["welcome"], reply_markup=keyboard)
