"""Лимиты и баланс пользователей."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bot.db import Database
from bot.payments.products import Product, load_products


class UsageService:
    """
    Приоритет списания:
    1. limits.enabled=false → без ограничений
    2. Активный безлимит → без списания
    3. Бесплатные запросы за сегодня (daily_usage по дате в timezone)
    4. Платные кредиты
    """

    def __init__(self, config: dict | None, db: Database) -> None:
        cfg = config or {}
        limits = cfg.get("limits", {})
        self.limits_enabled = bool(limits.get("enabled", True))
        self.free_daily_limit = int(limits.get("free_daily_limit", 3))
        self.timezone = ZoneInfo(limits.get("timezone", "UTC"))

        payments_cfg = cfg.get("payments", {})
        self.products = load_products(payments_cfg)
        self.unlimited_days = int(payments_cfg.get("unlimited_days", 30))
        self.db = db

    def _today(self) -> str:
        return datetime.now(self.timezone).date().isoformat()

    async def _run(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    def _grant_product_sync(self, user_id: int, product_id: str) -> str:
        product = self.products[product_id]
        if product.credits > 0:
            self.db.add_credits(user_id, product.credits)
            return f"Начислено {product.credits} поисков."
        until = self.db.extend_unlimited(user_id, product.unlimited_days)
        return f"Безлимит активен до {until.astimezone(self.timezone).strftime('%d.%m.%Y %H:%M')}."

    async def grant_product(self, user_id: int, product_id: str) -> str:
        return await self._run(self._grant_product_sync, user_id, product_id)

    async def can_search(self, user_id: int) -> tuple[bool, str | None]:
        if not self.limits_enabled:
            return True, None

        summary = await self.get_summary(user_id)
        if summary["unlimited_active"]:
            return True, None
        if summary["daily_left"] > 0:
            return True, None
        if summary["credits"] > 0:
            return True, None

        return False, (
            "Лимит исчерпан.\n\n"
            f"Бесплатно: {self.free_daily_limit} поиска в день.\n"
            "Купите пакет или безлимит — /buy"
        )

    async def record_search(self, user_id: int) -> None:
        if not self.limits_enabled:
            return

        await self._run(self._record_search_sync, user_id)

    def _record_search_sync(self, user_id: int) -> None:
        user = self.db.ensure_user(user_id)
        now = datetime.now(timezone.utc)
        if user.unlimited_until and user.unlimited_until > now:
            return

        today = self._today()
        daily_count = self.db.get_daily_count(user_id, today)
        if daily_count < self.free_daily_limit:
            self.db.increment_daily(user_id, today)
            return

        self.db.use_credit(user_id)

    async def touch_user(self, user_id: int) -> None:
        await self._run(self.db.ensure_user, user_id)

    async def get_summary(self, user_id: int) -> dict:
        return await self._run(
            self.db.get_user_summary,
            user_id,
            self._today(),
            self.free_daily_limit,
        )

    def get_product(self, product_id: str) -> Product:
        return self.products[product_id]

    async def create_payment(
        self,
        user_id: int,
        provider: str,
        product: str,
        external_id: str,
        amount: str,
    ) -> None:
        await self._run(
            self.db.create_payment,
            user_id,
            provider,
            product,
            external_id,
            amount,
        )

    async def complete_payment(self, external_id: str) -> tuple[int, str] | None:
        return await self._run(self.db.complete_payment, external_id)
