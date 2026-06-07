"""Лимиты и баланс пользователей."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bot.db import Database
from bot.i18n import Lang, lang_from_code, product_description, product_title, t
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
        self.free_daily_limit = int(limits.get("free_daily_limit", 5))
        self.timezone = ZoneInfo(limits.get("timezone", "UTC"))

        payments_cfg = cfg.get("payments", {})
        self.products = load_products(payments_cfg)
        self.unlimited_days = int(payments_cfg.get("unlimited_days", 30))
        self.db = db

    def _today(self) -> str:
        return datetime.now(self.timezone).date().isoformat()

    async def _run(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    def _user_lang(self, user_id: int) -> Lang:
        return lang_from_code(self.db.get_user_language(user_id))

    def _grant_product_sync(self, user_id: int, product_id: str, lang: Lang) -> str:
        product = self.products[product_id]
        if product.credits > 0:
            self.db.add_credits(user_id, product.credits)
            return t(lang, "granted_credits", credits=product.credits)
        until = self.db.extend_unlimited(user_id, product.unlimited_days)
        until_str = until.astimezone(self.timezone).strftime("%d.%m.%Y %H:%M")
        return t(lang, "granted_unlimited", until=until_str)

    async def grant_product(self, user_id: int, product_id: str, lang: Lang | None = None) -> str:
        resolved = lang or self._user_lang(user_id)
        return await self._run(self._grant_product_sync, user_id, product_id, resolved)

    async def can_search(
        self, user_id: int, lang: Lang | None = None
    ) -> tuple[bool, str | None]:
        if not self.limits_enabled:
            return True, None

        summary = await self.get_summary(user_id)
        if summary["unlimited_active"]:
            return True, None
        if summary["daily_left"] > 0:
            return True, None
        if summary["credits"] > 0:
            return True, None

        resolved = lang or self._user_lang(user_id)
        return False, t(resolved, "limit_exhausted", limit=self.free_daily_limit)

    def localized_product(self, product_id: str, lang: Lang) -> Product:
        product = self.products[product_id]
        return Product(
            id=product.id,
            title=product_title(
                lang,
                product_id,
                credits=product.credits,
                days=product.unlimited_days,
            ),
            description=product_description(
                lang,
                product_id,
                credits=product.credits,
                days=product.unlimited_days,
            ),
            credits=product.credits,
            unlimited_days=product.unlimited_days,
            stars_amount=product.stars_amount,
            usdt_amount=product.usdt_amount,
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

    async def touch_user(
        self, user_id: int, *, language_code: str | None = None
    ) -> None:
        await self._run(self._touch_user_sync, user_id, language_code)

    def _touch_user_sync(self, user_id: int, language_code: str | None) -> None:
        self.db.ensure_user(user_id)
        if language_code:
            self.db.set_user_language(user_id, language_code)

    def get_stored_lang(self, user_id: int) -> Lang:
        return self._user_lang(user_id)

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
