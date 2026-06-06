from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.analytics import EventLogger, classify_incoming


class AnalyticsMiddleware(BaseMiddleware):
    def __init__(self, analytics: EventLogger) -> None:
        super().__init__()
        self.analytics = analytics

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["analytics"] = self.analytics
        if isinstance(event, (Message, CallbackQuery)):
            classified = classify_incoming(event)
            if classified:
                user_id, event_name, meta = classified
                await self.analytics.log(user_id, event_name, **meta)
        return await handler(event, data)
