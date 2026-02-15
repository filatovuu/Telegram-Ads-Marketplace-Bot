import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = f"https://api.telegram.org/bot{settings.bot_token}"

# Cache bot info to avoid repeated API calls
_bot_info: dict | None = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
async def _call(method: str, **params: Any) -> dict:
    """Call Telegram Bot API and return the result dict, with retry."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{_BASE_URL}/{method}", json=params)
        data = resp.json()
    if not data.get("ok"):
        desc = data.get("description", "Unknown error")
        logger.error("Telegram API error: %s → %s", method, desc)
        raise ValueError(desc)
    return data["result"]


async def get_me() -> dict:
    """Get bot's own info (id, username, etc.). Cached after first call."""
    global _bot_info
    if _bot_info is None:
        _bot_info = await _call("getMe")
    return _bot_info


async def get_chat(chat_id: int | str) -> dict:
    """Fetch chat info (title, username, description, etc.)."""
    return await _call("getChat", chat_id=chat_id)


async def get_chat_member_count(chat_id: int | str) -> int:
    """Return subscriber count for a channel/group."""
    return await _call("getChatMemberCount", chat_id=chat_id)


async def get_chat_member(chat_id: int | str, user_id: int) -> dict:
    """Check a user's membership status in a chat."""
    return await _call("getChatMember", chat_id=chat_id, user_id=user_id)


async def send_message(
    chat_id: int | str, text: str, entities: list | None = None, parse_mode: str | None = None,
    reply_markup: dict | None = None,
) -> dict:
    """Send a text message to a chat."""
    params: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if entities:
        params["entities"] = entities
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup:
        params["reply_markup"] = reply_markup
    return await _call("sendMessage", **params)


async def send_photo(
    chat_id: int | str, photo: str, caption: str | None = None, caption_entities: list | None = None,
) -> dict:
    """Send a photo to a chat. `photo` can be a file_id or URL."""
    params: dict[str, Any] = {"chat_id": chat_id, "photo": photo}
    if caption:
        params["caption"] = caption
    if caption_entities:
        params["caption_entities"] = caption_entities
    return await _call("sendPhoto", **params)


async def send_video(
    chat_id: int | str, video: str, caption: str | None = None, caption_entities: list | None = None,
) -> dict:
    """Send a video to a chat. `video` can be a file_id or URL."""
    params: dict[str, Any] = {"chat_id": chat_id, "video": video}
    if caption:
        params["caption"] = caption
    if caption_entities:
        params["caption_entities"] = caption_entities
    return await _call("sendVideo", **params)


async def send_document(
    chat_id: int | str, document: str, caption: str | None = None, caption_entities: list | None = None,
) -> dict:
    """Send a document to a chat."""
    params: dict[str, Any] = {"chat_id": chat_id, "document": document}
    if caption:
        params["caption"] = caption
    if caption_entities:
        params["caption_entities"] = caption_entities
    return await _call("sendDocument", **params)


async def send_animation(
    chat_id: int | str, animation: str, caption: str | None = None, caption_entities: list | None = None,
) -> dict:
    """Send an animation (GIF) to a chat."""
    params: dict[str, Any] = {"chat_id": chat_id, "animation": animation}
    if caption:
        params["caption"] = caption
    if caption_entities:
        params["caption_entities"] = caption_entities
    return await _call("sendAnimation", **params)


async def send_media_group(
    chat_id: int | str,
    media: list[dict],
    caption: str | None = None,
    caption_entities: list | None = None,
) -> list[dict]:
    """Send a media group (album) to a chat.

    Each item in ``media`` must have ``file_id`` and ``type`` keys.
    Caption and entities are attached to the first item.
    Returns a list of sent Message objects.
    """
    input_media = []
    for i, item in enumerate(media):
        entry: dict[str, Any] = {"type": item["type"], "media": item["file_id"]}
        if i == 0:
            if caption:
                entry["caption"] = caption
            if caption_entities:
                entry["caption_entities"] = caption_entities
        input_media.append(entry)
    return await _call("sendMediaGroup", chat_id=chat_id, media=input_media)


async def forward_message(chat_id: int | str, from_chat_id: int | str, message_id: int) -> dict:
    """Forward a message from one chat to another."""
    return await _call("forwardMessage", chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)


async def copy_message(chat_id: int | str, from_chat_id: int | str, message_id: int) -> dict:
    """Copy a message from one chat to another (without the forward header)."""
    return await _call("copyMessage", chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)


async def delete_message(chat_id: int | str, message_id: int) -> bool:
    """Delete a message from a chat."""
    return await _call("deleteMessage", chat_id=chat_id, message_id=message_id)
