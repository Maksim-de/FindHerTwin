"""Меню бота: команды Telegram и клавиатура внизу чата."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.i18n import Lang, all_variants, t

CALLBACK_NEW_PHOTO = "act:new_photo"

# Для обратной совместимости фильтров
BTN_NEW_PHOTO = "📷 Новое фото"
BTN_BUY = "💎 Тарифы"
BTN_BALANCE = "📊 Баланс"
BTN_HELP = "❓ Помощь"

BTN_NEW_PHOTO_ALL = all_variants("btn_new_photo")
BTN_BUY_ALL = all_variants("btn_buy")
BTN_BALANCE_ALL = all_variants("btn_balance")
BTN_HELP_ALL = all_variants("btn_help")


def main_menu_keyboard(lang: Lang = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_new_photo"))],
            [
                KeyboardButton(text=t(lang, "btn_buy")),
                KeyboardButton(text=t(lang, "btn_balance")),
            ],
            [KeyboardButton(text=t(lang, "btn_help"))],
        ],
        resize_keyboard=True,
        input_field_placeholder=t(lang, "input_placeholder"),
    )


async def setup_bot_commands(bot: Bot) -> None:
    for lang in ("ru", "en"):
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=t(lang, "cmd_start")),
                BotCommand(command="search", description=t(lang, "cmd_search")),
                BotCommand(command="buy", description=t(lang, "cmd_buy")),
                BotCommand(command="balance", description=t(lang, "cmd_balance")),
                BotCommand(command="help", description=t(lang, "cmd_help")),
            ],
            language_code=lang,
        )
