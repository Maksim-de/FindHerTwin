"""Язык пользователя и сохранение language_code в БД."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.i18n import user_lang
from bot.usage import UsageService


class LocaleMiddleware(BaseMiddleware):
    def __init__(self, usage_service: UsageService) -> None:
        super().__init__()
        self.usage_service = usage_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        lang = user_lang(tg_user)
        data["lang"] = lang
        if tg_user is not None:
            await self.usage_service.touch_user(
                tg_user.id,
                language_code=tg_user.language_code,
            )
        return await handler(event, data)
