#!/usr/bin/env python3
"""
Telegram-бот: поиск похожих порноактрис по фото.

Запуск:
  export TELEGRAM_BOT_TOKEN=your_token
  python -m bot.main

Токен: @BotFather в Telegram → /newbot
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import face.bootstrap  # noqa: F401, E402

from bot.db import Database
from bot.digest import run_digest_scheduler
from bot.handlers import router as search_router
from bot.menu import setup_bot_commands
from bot.analytics import EventLogger
from bot.analytics_middleware import AnalyticsMiddleware
from bot.locale_middleware import LocaleMiddleware
from bot.middleware import InjectMiddleware
from bot.payment_handlers import router as payment_router
from bot.payments.crypto_pay import CryptoPayClient
from bot.usage import UsageService
from face.dataset_status import describe_dataset, resolve_data_root
from face.search_service import FaceSearchService

load_dotenv(PROJECT_ROOT / ".env")


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "bot.log", encoding="utf-8"),
        ],
    )


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Добавьте в .env или экспортируйте в shell."
        )

    config_path = PROJECT_ROOT / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    paths = config.get("paths", {})
    setup_logging(PROJECT_ROOT / paths.get("logs", "logs"))

    telegram_cfg = config.get("telegram", {})
    payments_cfg = telegram_cfg.get("payments", {})
    db_path = PROJECT_ROOT / telegram_cfg.get("database", "data/bot.db")

    temp_dir = PROJECT_ROOT / "bot" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    data_root = resolve_data_root(PROJECT_ROOT)
    welcome_photo_cfg = telegram_cfg.get("welcome_photo")
    welcome_photo = None
    if welcome_photo_cfg:
        welcome_photo = PROJECT_ROOT / welcome_photo_cfg
        if not welcome_photo.exists():
            rel = Path(welcome_photo_cfg)
            if rel.parts and rel.parts[0] == "data":
                welcome_photo = data_root / Path(*rel.parts[1:])
        if not welcome_photo.exists():
            logging.warning("welcome_photo не найден: %s", welcome_photo_cfg)
            welcome_photo = None

    logging.info("Data: %s", describe_dataset(data_root, project_root=PROJECT_ROOT))
    logging.info("Инициализация моделей поиска...")
    search_service = FaceSearchService(config_path)
    if search_service.is_stub_dataset:
        logging.warning(
            "Режим заглушки: %s",
            describe_dataset(search_service.data_root, project_root=PROJECT_ROOT),
        )
    db = Database(db_path)
    usage_service = UsageService(telegram_cfg, db)

    crypto_token = os.getenv("CRYPTO_PAY_TOKEN", "").strip()
    crypto_testnet = os.getenv("CRYPTO_PAY_TESTNET", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    crypto_pay = CryptoPayClient(crypto_token, testnet=crypto_testnet)
    stars_enabled = bool(payments_cfg.get("stars_enabled", True))
    crypto_enabled = bool(payments_cfg.get("crypto_enabled", True))

    if not crypto_pay.enabled:
        logging.warning("CRYPTO_PAY_TOKEN не задан — оплата USDT отключена")
    if telegram_cfg.get("limits", {}).get("enabled", True):
        logging.info(
            "Лимиты: %s бесплатных/день",
            usage_service.free_daily_limit,
        )
    else:
        logging.info("Лимиты отключены (limits.enabled: false)")

    analytics_cfg = telegram_cfg.get("analytics", {})
    analytics = EventLogger(
        PROJECT_ROOT / analytics_cfg.get("events_file", "logs/events.jsonl"),
        enabled=bool(analytics_cfg.get("enabled", True)),
    )

    bot = Bot(token=token)
    await setup_bot_commands(bot)
    dp = Dispatcher()
    analytics_mw = AnalyticsMiddleware(analytics)
    dp.message.middleware(analytics_mw)
    dp.callback_query.middleware(analytics_mw)

    locale_mw = LocaleMiddleware(usage_service)
    search_router.message.middleware(locale_mw)
    search_router.callback_query.middleware(locale_mw)
    payment_router.message.middleware(locale_mw)
    payment_router.callback_query.middleware(locale_mw)

    middleware = InjectMiddleware(
        search_service,
        usage_service,
        crypto_pay,
        stars_enabled,
        crypto_enabled,
        temp_dir,
        welcome_photo=welcome_photo,
    )
    search_router.message.middleware(middleware)
    search_router.callback_query.middleware(middleware)
    payment_router.message.middleware(middleware)
    payment_router.callback_query.middleware(middleware)
    dp.include_router(payment_router)
    dp.include_router(search_router)

    digest_cfg = telegram_cfg.get("digest", {})
    digest_task = asyncio.create_task(
        run_digest_scheduler(bot, db, search_service, digest_cfg, analytics)
    )

    logging.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        digest_task.cancel()
        try:
            await digest_task
        except asyncio.CancelledError:
            pass
        await crypto_pay.close()


if __name__ == "__main__":
    asyncio.run(main())
