"""Меню бота: команды Telegram и клавиатура внизу чата."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Тексты кнопок reply-клавиатуры
BTN_NEW_PHOTO = "📷 Новое фото"
BTN_BUY = "💎 Тарифы"
BTN_BALANCE = "📊 Баланс"
BTN_HELP = "❓ Помощь"

CALLBACK_NEW_PHOTO = "act:new_photo"

NEW_PHOTO_PROMPT = (
    "Отправьте <b>новое фото</b> девушки как изображение (не файл).\n\n"
    "Лицо крупно и чётко — так точнее."
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW_PHOTO)],
            [KeyboardButton(text=BTN_BUY), KeyboardButton(text=BTN_BALANCE)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте фото для поиска…",
    )


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать"),
            BotCommand(command="search", description="Поиск по фото"),
            BotCommand(command="buy", description="Тарифы и оплата"),
            BotCommand(command="balance", description="Мой баланс"),
            BotCommand(command="help", description="Как пользоваться"),
        ]
    )
