"""Middleware to collect Telegram media-group (album) messages into a single handler call.

Telegram delivers each item in an album as a separate Message object sharing
the same ``media_group_id``.  Without this middleware, the handler would be
called once per item and only capture the first file.

How it works:
1. Message arrives with ``media_group_id`` → buffer it.
2. First message in a group **blocks inline** (``await asyncio.sleep``).
3. Subsequent messages append to the buffer and return immediately.
4. After ``latency`` seconds of silence the first coroutine wakes up,
   sets ``data["album"]`` and calls the handler **once**.
5. Messages without ``media_group_id`` pass through unmodified.

Prerequisites:
  The webhook endpoint MUST dispatch album messages via
  ``asyncio.create_task`` so that all items in the group run concurrently.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 1.0) -> None:
        super().__init__()
        self.latency = latency
        self._albums: Dict[str, list[Message]] = {}
        self._counters: Dict[str, int] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        media_group_id = event.media_group_id
        if media_group_id is None:
            return await handler(event, data)

        # Buffer the message
        is_first = media_group_id not in self._albums
        if is_first:
            self._albums[media_group_id] = []
            self._counters[media_group_id] = 0

        self._albums[media_group_id].append(event)
        self._counters[media_group_id] += 1

        if not is_first:
            # Not the first message — just buffered, return immediately.
            # The first message's coroutine will pick it up.
            return

        # First message — wait inline until no new items arrive
        try:
            while True:
                count_before = self._counters[media_group_id]
                await asyncio.sleep(self.latency)
                count_after = self._counters.get(media_group_id, 0)
                if count_after == count_before:
                    break
                # New items arrived during sleep — wait again

            album = self._albums.pop(media_group_id, [])
            self._counters.pop(media_group_id, None)

            if not album:
                return

            data["album"] = album
            return await handler(event, data)
        except Exception:
            logger.exception("AlbumMiddleware error for group %s", media_group_id)
            self._albums.pop(media_group_id, None)
            self._counters.pop(media_group_id, None)
