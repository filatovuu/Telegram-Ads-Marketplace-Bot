import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    MenuButtonWebApp,
    Update,
    WebAppInfo,
)
from fastapi import FastAPI, Request, Response

from app.config import settings
from handlers.deals import router as deals_router
from handlers.start import router as start_router
from handlers.callbacks import router as callbacks_router
from handlers.channel_posts import router as channel_posts_router
from handlers.chat_member import router as chat_member_router
from middleware.album import AlbumMiddleware
from middleware.auth import AuthMiddleware
from middleware.i18n import I18nMiddleware

logger = logging.getLogger(__name__)

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())

# Register middlewares (order matters: album first, then auth, then i18n)
dp.message.middleware(AlbumMiddleware())
dp.message.middleware(AuthMiddleware())
dp.message.middleware(I18nMiddleware())
dp.callback_query.middleware(AuthMiddleware())
dp.callback_query.middleware(I18nMiddleware())

# Register routers (deals first for priority matching of deal: callbacks)
dp.include_router(deals_router)
dp.include_router(start_router)
dp.include_router(callbacks_router)
dp.include_router(channel_posts_router)
dp.include_router(chat_member_router)


async def _call_with_retry(coro_factory, retries=3):
    """Call an async function, retrying on TelegramRetryAfter (flood control)."""
    for attempt in range(retries):
        try:
            return await coro_factory()
        except TelegramRetryAfter as e:
            if attempt == retries - 1:
                raise
            logger.warning("Flood control, retrying in %s seconds", e.retry_after)
            await asyncio.sleep(e.retry_after)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: register webhook (with retry for multi-worker flood control)
    await _call_with_retry(lambda: bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret,
        allowed_updates=[
            "message",
            "callback_query",
            "channel_post",
            "edited_channel_post",
            "my_chat_member",
        ],
        drop_pending_updates=False,
    ))
    logger.info("Webhook set to %s", settings.webhook_url)

    # Set bot commands (EN)
    await _call_with_retry(lambda: bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="deals", description="My deals"),
            BotCommand(command="help", description="Help & info"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
        language_code="en",
    ))
    # Set bot commands (RU)
    await _call_with_retry(lambda: bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="deals", description="Мои сделки"),
            BotCommand(command="help", description="Помощь"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
        language_code="ru",
    ))
    # Default commands (fallback)
    await _call_with_retry(lambda: bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="deals", description="My deals"),
            BotCommand(command="help", description="Help & info"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    ))

    # Set menu button → Mini App
    await _call_with_retry(lambda: bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open",
            web_app=WebAppInfo(url=settings.mini_app_url),
        ),
    ))
    logger.info("Bot commands and menu button configured")
    yield
    # Shutdown: delete webhook and close bot session
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()
    logger.info("Webhook deleted, bot session closed")


app = FastAPI(lifespan=lifespan)


async def _safe_feed_update(update: Update) -> None:
    """Process an update in the background, catching exceptions."""
    try:
        await dp.feed_update(bot=bot, update=update)
    except Exception:
        logger.exception("Error processing background update %s", update.update_id)


@app.post("/bot/webhook")
async def webhook_handler(request: Request) -> Response:
    """Handle incoming Telegram webhook updates.

    Album messages (with media_group_id) are processed in a background task
    so that Telegram sends all album items without waiting for the previous
    one to finish.  AlbumMiddleware then collects them within its latency
    window and calls the handler once with the full album.
    """
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.webhook_secret:
        return Response(status_code=403)

    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})

    # Album items must be processed concurrently — respond 200 immediately
    msg = update.message
    if msg and msg.media_group_id:
        asyncio.create_task(_safe_feed_update(update))
    else:
        await dp.feed_update(bot=bot, update=update)

    return Response(status_code=200)


@app.get("/bot/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
