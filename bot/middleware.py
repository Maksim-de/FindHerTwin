from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.payments.crypto_pay import CryptoPayClient
from bot.usage import UsageService
from face.search_service import FaceSearchService


class InjectMiddleware(BaseMiddleware):
    def __init__(
        self,
        search_service: FaceSearchService,
        usage_service: UsageService,
        crypto_pay: CryptoPayClient,
        stars_enabled: bool,
        crypto_enabled: bool,
        temp_dir: Path,
        welcome_photo: Path | None = None,
    ) -> None:
        super().__init__()
        self.search_service = search_service
        self.usage_service = usage_service
        self.crypto_pay = crypto_pay
        self.stars_enabled = stars_enabled
        self.crypto_enabled = crypto_enabled and crypto_pay.enabled
        self.temp_dir = temp_dir
        self.welcome_photo = welcome_photo

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["search_service"] = self.search_service
        data["usage_service"] = self.usage_service
        data["crypto_pay"] = self.crypto_pay
        data["stars_enabled"] = self.stars_enabled
        data["crypto_enabled"] = self.crypto_enabled
        data["temp_dir"] = self.temp_dir
        data["welcome_photo"] = self.welcome_photo
        if "analytics" not in data:
            data["analytics"] = None
        return await handler(event, data)
