"""Локализация: ru для language_code ru*, иначе en."""

from __future__ import annotations

from typing import Any

from aiogram.types import User

Lang = str

TEXTS: dict[Lang, dict[str, str]] = {
    "ru": {
        "btn_new_photo": "📷 Новое фото",
        "btn_buy": "💎 Тарифы",
        "btn_balance": "📊 Баланс",
        "btn_help": "❓ Помощь",
        "input_placeholder": "Отправьте фото для поиска…",
        "cmd_start": "Начать",
        "cmd_search": "Поиск по фото",
        "cmd_buy": "Тарифы и оплата",
        "cmd_balance": "Мой баланс",
        "cmd_help": "Как пользоваться",
        "welcome_intro": (
            "Привет! Я ищу похожих порноактрис по фото.\n\n"
            "Отправьте фотографию девушки — верну top-5 похожих порноактрис."
        ),
        "welcome_limits_free": "🆓 {limit} бесплатных поиска в день",
        "welcome_limits_off": "🧪 Тестовый режим — лимиты отключены",
        "welcome_pack": "💎 {credits} поисков — ${price}",
        "welcome_unlimited": "♾ {title} — ${price}",
        "welcome_footer": "Меню внизу — поиск, тарифы, баланс.",
        "new_photo_prompt": (
            "Отправьте <b>новое фото</b> девушки как изображение (не файл).\n\n"
            "Лицо крупно и чётко — так точнее."
        ),
        "help_text": (
            "<b>Как пользоваться</b>\n\n"
            "1. Отправьте фото (не как файл, а как изображение)\n"
            "2. Дождитесь анализа (~3–5 сек)\n"
            "3. Получите top-5 с фото лучшего совпадения\n"
            "4. Кнопки <b>1–5</b> — переключение между актрисами\n"
            "5. <b>⭐ Дня</b> — актриса дня (в подборке)\n"
            "6. <b>Найти похожих</b> — похожие на выбранную\n"
            "7. <b>Новое фото</b> — новый поиск\n\n"
            "<b>Меню внизу:</b> 📷 Новое фото · 💎 Тарифы · 📊 Баланс · ❓ Помощь\n\n"
            "<b>Советы для точности</b>\n"
            "• Лицо крупно и чётко\n"
            "• Анфас или лёгкий поворот\n"
            "• Без сильных фильтров\n\n"
            "<i>Score &gt; 70% — уверенное совпадение</i>"
        ),
        "dataset_status_title": "Статус датасета",
        "dataset_stub": "заглушка",
        "dataset_ready": "поиск включён",
        "analyzing": "Анализирую фото…",
        "download_failed": "Не удалось скачать фото.",
        "search_error": "Произошла ошибка при обработке. Попробуйте позже.",
        "limit_exhausted": (
            "Лимит исчерпан.\n\n"
            "Бесплатно: {limit} поиска в день.\n"
            "Купите пакет или безлимит — /buy"
        ),
        "limit_fallback": "Лимит запросов исчерпан.",
        "stub_dataset": (
            "⏳ <b>Бот запущен, индекс ещё не готов.</b>\n\n"
            "Загрузите датасет на сервер и перезапустите бот."
        ),
        "session_expired": "Сессия устарела — отправьте фото снова",
        "stale_button": "Устаревшая кнопка",
        "no_such_rank": "Нет такой позиции",
        "bad_payload": "Некорректные данные",
        "update_photo_failed": "Не удалось обновить фото. Попробуйте ещё раз.",
        "dataset_not_loaded": "Датасет ещё не загружен",
        "similar_search": "Ищу похожих на <b>{name}</b>…",
        "similar_error": "Произошла ошибка. Попробуйте позже.",
        "send_as_image": (
            "Отправьте фото как <b>изображение</b>, не как файл.\n"
            "Или сожмите фото — Telegram пришлёт его как картинку."
        ),
        "send_photo_prompt": "Пришлите фотографию девушки для поиска.",
        "fallback_hint": "Нажмите <b>📷 Новое фото</b> в меню или просто пришлите изображение.",
        "no_face": (
            "Лицо не найдено на фото.\n\n"
            "Попробуйте другое: лицо крупно, анфас, хорошее освещение."
        ),
        "no_safe_photo": "Нет safe-фото (только explicit-кадры).",
        "top5_title": "<b>Top-5 похожих актрис:</b>",
        "similar_to": "Похожие на <b>{name}</b>",
        "digest_title": "🎲 <b>Актриса дня: {name}</b>",
        "digest_star": "<b>⭐ {name} — актриса дня</b>",
        "match_line": "<b>#{rank} {name} — {score}%</b>",
        "btn_find_similar": "🔍 Найти похожих",
        "btn_new_photo_inline": "📷 Новое фото",
        "btn_star_of_day": "⭐ Дня",
        "balance_title": "<b>Баланс</b>",
        "balance_limits_off": "Лимиты отключены (тестовый режим).",
        "balance_unlimited": "♾ Безлимит до: <b>{until}</b>",
        "balance_free": "🆓 Бесплатно сегодня: <b>{left}</b> из {limit}",
        "balance_credits": "💳 Платные поиски: <b>{credits}</b>",
        "balance_footer": "Тарифы: /buy",
        "buy_title": "<b>Тарифы</b>",
        "buy_free": "🆓 <b>Бесплатно</b> — {limit} поиска в день",
        "buy_choose": "Выберите способ оплаты:",
        "product_pack_title": "{credits} поисков",
        "product_pack_desc": "Пакет из {credits} поисков (разовая покупка)",
        "product_unlimited_title": "Безлимит на {days} дн.",
        "product_unlimited_desc": "Неограниченные поиски на {days} дней",
        "stars_disabled": "Оплата Stars отключена",
        "crypto_disabled": "Crypto Pay не настроен",
        "invoice_failed": "Не удалось создать счёт",
        "crypto_pay_btn": "Оплатить в CryptoBot",
        "crypto_check_btn": "Проверить оплату",
        "crypto_invoice": (
            "<b>{title}</b>\n"
            "Сумма: <b>{amount} USDT</b>\n\n"
            "Нажмите «Оплатить», затем «Проверить оплату»."
        ),
        "crypto_check_error": "Ошибка проверки",
        "crypto_not_paid": "Оплата ещё не поступила",
        "already_granted": "Уже начислено",
        "not_your_payment": "Это не ваш платёж",
        "payment_done": "Готово!",
        "payment_received": "✅ Оплата получена!\n{details}",
        "payment_support": "Оплата получена, но не удалось начислить. Напишите в поддержку.",
        "payment_user_error": "Ошибка начисления. Напишите в поддержку.",
        "payment_duplicate": "Платёж уже был обработан ранее.",
        "granted_credits": "Начислено {credits} поисков.",
        "granted_unlimited": "Безлимит активен до {until}.",
    },
    "en": {
        "btn_new_photo": "📷 New photo",
        "btn_buy": "💎 Plans",
        "btn_balance": "📊 Balance",
        "btn_help": "❓ Help",
        "input_placeholder": "Send a photo to search…",
        "cmd_start": "Start",
        "cmd_search": "Search by photo",
        "cmd_buy": "Plans & payment",
        "cmd_balance": "My balance",
        "cmd_help": "How to use",
        "welcome_intro": (
            "Hi! I find similar adult actresses from a photo.\n\n"
            "Send a photo — I'll return the top-5 closest matches."
        ),
        "welcome_limits_free": "🆓 {limit} free searches per day",
        "welcome_limits_off": "🧪 Test mode — no limits",
        "welcome_pack": "💎 {credits} searches — ${price}",
        "welcome_unlimited": "♾ {title} — ${price}",
        "welcome_footer": "Use the menu below — search, plans, balance.",
        "new_photo_prompt": (
            "Send a <b>new photo</b> as an image (not as a file).\n\n"
            "Face large and clear works best."
        ),
        "help_text": (
            "<b>How to use</b>\n\n"
            "1. Send a photo (as image, not as file)\n"
            "2. Wait ~3–5 sec for analysis\n"
            "3. Get top-5 with the best match photo\n"
            "4. Buttons <b>1–5</b> — switch between matches\n"
            "5. <b>⭐ Pick</b> — actress of the day (in digest)\n"
            "6. <b>Find similar</b> — similar to the selected one\n"
            "7. <b>New photo</b> — new search\n\n"
            "<b>Menu:</b> 📷 New photo · 💎 Plans · 📊 Balance · ❓ Help\n\n"
            "<b>Tips</b>\n"
            "• Face large and sharp\n"
            "• Front or slight angle\n"
            "• Avoid heavy filters\n\n"
            "<i>Score &gt; 70% — strong match</i>"
        ),
        "dataset_status_title": "Dataset status",
        "dataset_stub": "stub",
        "dataset_ready": "search enabled",
        "analyzing": "Analyzing photo…",
        "download_failed": "Could not download the photo.",
        "search_error": "Something went wrong. Please try again later.",
        "limit_exhausted": (
            "Limit reached.\n\n"
            "Free: {limit} searches per day.\n"
            "Buy a pack or unlimited — /buy"
        ),
        "limit_fallback": "Search limit reached.",
        "stub_dataset": (
            "⏳ <b>Bot is running, index is not ready yet.</b>\n\n"
            "Upload the dataset to the server and restart the bot."
        ),
        "session_expired": "Session expired — send a photo again",
        "stale_button": "Outdated button",
        "no_such_rank": "No such result",
        "bad_payload": "Invalid data",
        "update_photo_failed": "Could not update photo. Try again.",
        "dataset_not_loaded": "Dataset not loaded yet",
        "similar_search": "Finding matches similar to <b>{name}</b>…",
        "similar_error": "Something went wrong. Try again later.",
        "send_as_image": (
            "Send the photo as an <b>image</b>, not as a file.\n"
            "Or compress it — Telegram will send it as a picture."
        ),
        "send_photo_prompt": "Send a photo to search.",
        "fallback_hint": "Tap <b>📷 New photo</b> in the menu or send an image.",
        "no_face": (
            "No face found in the photo.\n\n"
            "Try another: face large, front-facing, good lighting."
        ),
        "no_safe_photo": "No SFW photo (explicit frames only).",
        "top5_title": "<b>Top-5 similar actresses:</b>",
        "similar_to": "Similar to <b>{name}</b>",
        "digest_title": "🎲 <b>Actress of the day: {name}</b>",
        "digest_star": "<b>⭐ {name} — actress of the day</b>",
        "match_line": "<b>#{rank} {name} — {score}%</b>",
        "btn_find_similar": "🔍 Find similar",
        "btn_new_photo_inline": "📷 New photo",
        "btn_star_of_day": "⭐ Pick",
        "balance_title": "<b>Balance</b>",
        "balance_limits_off": "Limits disabled (test mode).",
        "balance_unlimited": "♾ Unlimited until: <b>{until}</b>",
        "balance_free": "🆓 Free today: <b>{left}</b> of {limit}",
        "balance_credits": "💳 Paid searches: <b>{credits}</b>",
        "balance_footer": "Plans: /buy",
        "buy_title": "<b>Plans</b>",
        "buy_free": "🆓 <b>Free</b> — {limit} searches per day",
        "buy_choose": "Choose payment method:",
        "product_pack_title": "{credits} searches",
        "product_pack_desc": "Pack of {credits} searches (one-time)",
        "product_unlimited_title": "Unlimited for {days} days",
        "product_unlimited_desc": "Unlimited searches for {days} days",
        "stars_disabled": "Stars payments disabled",
        "crypto_disabled": "Crypto Pay not configured",
        "invoice_failed": "Could not create invoice",
        "crypto_pay_btn": "Pay in CryptoBot",
        "crypto_check_btn": "Check payment",
        "crypto_invoice": (
            "<b>{title}</b>\n"
            "Amount: <b>{amount} USDT</b>\n\n"
            "Tap Pay, then Check payment."
        ),
        "crypto_check_error": "Check failed",
        "crypto_not_paid": "Payment not received yet",
        "already_granted": "Already credited",
        "not_your_payment": "Not your payment",
        "payment_done": "Done!",
        "payment_received": "✅ Payment received!\n{details}",
        "payment_support": "Payment received but credit failed. Contact support.",
        "payment_user_error": "Credit error. Contact support.",
        "payment_duplicate": "Payment was already processed.",
        "granted_credits": "Added {credits} searches.",
        "granted_unlimited": "Unlimited until {until}.",
    },
}


def normalize_lang(code: str | None) -> Lang:
    if code and code.lower().startswith("ru"):
        return "ru"
    return "en"


def user_lang(user: User | None) -> Lang:
    if user is None:
        return "en"
    return normalize_lang(user.language_code)


def lang_from_code(code: str | None) -> Lang:
    return normalize_lang(code)


def t(lang: Lang, key: str, **kwargs: Any) -> str:
    table = TEXTS.get(lang, TEXTS["en"])
    text = table.get(key, TEXTS["en"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text


def all_variants(key: str) -> set[str]:
    return {TEXTS["ru"][key], TEXTS["en"][key]}


def help_text_bilingual() -> str:
    return f"{t('ru', 'help_text')}\n\n──────────\n\n{t('en', 'help_text')}"


def product_title(lang: Lang, product_id: str, *, credits: int, days: int) -> str:
    if product_id == "pack_15":
        return t(lang, "product_pack_title", credits=credits)
    return t(lang, "product_unlimited_title", days=days)


def product_description(lang: Lang, product_id: str, *, credits: int, days: int) -> str:
    if product_id == "pack_15":
        return t(lang, "product_pack_desc", credits=credits)
    return t(lang, "product_unlimited_desc", days=days)
