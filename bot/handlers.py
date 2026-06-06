from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.analytics import EventLogger
from bot.menu import (
    BTN_BALANCE,
    BTN_BUY,
    BTN_HELP,
    BTN_NEW_PHOTO,
    CALLBACK_NEW_PHOTO,
    NEW_PHOTO_PROMPT,
    main_menu_keyboard,
)
from bot.results_ui import (
    CALLBACK_NAV,
    CALLBACK_SIMILAR,
    deliver_search_results,
    parse_session_callback,
    resolve_view,
    session_cache,
    session_to_matches,
    update_match_card,
)
from bot.usage import UsageService
from face.search_service import FaceSearchService

logger = logging.getLogger(__name__)

router = Router()

STUB_DATASET_MESSAGE = (
    "⏳ <b>Бот запущен, датасет ещё не загружен.</b>\n\n"
    "В Amvera: Репозиторий → <b>Data</b> → загрузите папки "
    "<code>index</code>, <code>raw</code>, <code>processed</code>, <code>metadata</code>.\n"
    "После загрузки перезапустите приложение — поиск заработает."
)


def _welcome_text(usage_service: UsageService) -> str:
    limits_line = (
        f"🆓 {usage_service.free_daily_limit} бесплатных поиска в день"
        if usage_service.limits_enabled
        else "🧪 Тестовый режим — лимиты отключены"
    )
    pack = usage_service.products["pack_15"]
    unlimited = usage_service.products["unlimited"]
    return (
        "Привет! Я ищу похожих порноактрис по фото.\n\n"
        "Отправьте фотографию девушки — верну top-5 похожих порноактрис.\n\n"
        f"{limits_line}\n"
        f"💎 {pack.credits} поисков — ${pack.usdt_amount}\n"
        f"♾ {unlimited.title} — ${unlimited.usdt_amount}\n\n"
        "Меню внизу — поиск, тарифы, баланс."
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    usage_service: UsageService,
    welcome_photo: Path | None = None,
) -> None:
    if message.from_user:
        await usage_service.touch_user(message.from_user.id)

    text = _welcome_text(usage_service)
    keyboard = main_menu_keyboard()

    if welcome_photo and welcome_photo.exists():
        await message.answer_photo(
            FSInputFile(welcome_photo),
            caption=text,
            reply_markup=keyboard,
        )
        return

    await message.answer(text, reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
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
        "<i>Score &gt; 70% — уверенное совпадение</i>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    await message.answer(NEW_PHOTO_PROMPT, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(F.text == BTN_NEW_PHOTO)
async def menu_new_photo(message: Message) -> None:
    await message.answer(NEW_PHOTO_PROMPT, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == CALLBACK_NEW_PHOTO)
async def inline_new_photo(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer(
            NEW_PHOTO_PROMPT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    await callback.answer()


@router.message(F.photo)
async def handle_photo(
    message: Message,
    bot: Bot,
    search_service: FaceSearchService,
    usage_service: UsageService,
    temp_dir: Path,
    analytics: EventLogger | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await usage_service.touch_user(user_id)

    allowed, reason = await usage_service.can_search(user_id)
    if not allowed:
        if analytics:
            await analytics.log(user_id, "limit_denied", action="photo_search")
        await message.answer(reason or "Лимит запросов исчерпан.", parse_mode="HTML")
        return

    if search_service.is_stub_dataset:
        await message.answer(STUB_DATASET_MESSAGE, parse_mode="HTML")
        return

    status_msg = await message.answer("Анализирую фото…")

    photo = message.photo[-1]
    temp_path = temp_dir / f"{user_id}_{photo.file_id}.jpg"

    try:
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            await status_msg.edit_text("Не удалось скачать фото.")
            return
        await bot.download_file(file.file_path, destination=temp_path)

        embedding = await asyncio.to_thread(search_service.encode_image, temp_path)
        matches = (
            await asyncio.to_thread(search_service.search_from_embedding, embedding)
            if embedding is not None
            else []
        )
        await usage_service.record_search(user_id)
        if analytics:
            await analytics.log(
                user_id,
                "search_completed",
                kind="photo",
                matches=len(matches),
                top_slug=matches[0].slug if matches else None,
            )

        query_vec = embedding.astype(float).tolist() if embedding is not None else None
        await status_msg.delete()
        await deliver_search_results(
            message,
            bot,
            matches,
            search_service,
            user_id,
            query_embedding=query_vec,
        )
    except Exception as exc:
        logger.exception("Ошибка поиска для user=%s: %s", user_id, exc)
        if analytics:
            await analytics.log(user_id, "search_failed", kind="photo")
        await status_msg.edit_text("Произошла ошибка при обработке. Попробуйте позже.")
    finally:
        temp_path.unlink(missing_ok=True)


@router.callback_query(F.data.startswith(CALLBACK_NAV))
async def handle_nav(
    callback: CallbackQuery,
    bot: Bot,
    search_service: FaceSearchService,
) -> None:
    if not callback.message or not callback.from_user or not callback.data:
        await callback.answer()
        return

    parsed = parse_session_callback(callback.data.removeprefix(CALLBACK_NAV))
    if parsed is None:
        await callback.answer("Устаревшая кнопка", show_alert=True)
        return

    session_id, rank = parsed
    session = session_cache.get(session_id, callback.from_user.id)
    if session is None:
        await callback.answer("Сессия устарела — отправьте фото снова", show_alert=True)
        return

    current = resolve_view(search_service, session, rank)
    if current is None:
        await callback.answer("Нет такой позиции", show_alert=True)
        return

    matches = session_to_matches(search_service, session)
    try:
        await update_match_card(
            bot,
            callback.message,
            matches,
            current,
            rank,
            search_service,
            session_id,
            session,
        )
        await callback.answer()
    except Exception as exc:
        logger.exception("Ошибка nav rank=%s: %s", rank, exc)
        await callback.answer("Не удалось обновить фото", show_alert=True)


@router.callback_query(F.data.startswith(CALLBACK_SIMILAR))
async def handle_similar(
    callback: CallbackQuery,
    bot: Bot,
    search_service: FaceSearchService,
    usage_service: UsageService,
    analytics: EventLogger | None = None,
) -> None:
    if not callback.message or not callback.from_user or not callback.data:
        await callback.answer()
        return

    user_id = callback.from_user.id
    allowed, reason = await usage_service.can_search(user_id)
    if not allowed:
        if analytics:
            await analytics.log(user_id, "limit_denied", action="similar")
        await callback.answer(reason or "Лимит исчерпан", show_alert=True)
        return

    if search_service.is_stub_dataset:
        await callback.answer("Датасет ещё не загружен", show_alert=True)
        return

    payload = callback.data.removeprefix(CALLBACK_SIMILAR)
    parsed = parse_session_callback(payload)
    if parsed is not None:
        session_id, rank = parsed
        session = session_cache.get(session_id, user_id)
        if session is None:
            await callback.answer("Сессия устарела — отправьте фото снова", show_alert=True)
            return
        stored = session.get_view(rank)
        if stored is None:
            await callback.answer("Нет такой позиции", show_alert=True)
            return
        slug = stored.slug
        face_num = stored.face_num
        actress_name = stored.name
    else:
        slug, _, face_num = payload.rpartition(":")
        if not slug:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        actress_name = search_service.get_actress_name(slug)

    await callback.answer()
    status_msg = await callback.message.answer(
        f"Ищу похожих на <b>{actress_name}</b>…", parse_mode="HTML"
    )

    try:
        embedding = await asyncio.to_thread(
            search_service.get_actress_embedding, slug, face_num or None
        )
        matches = (
            await asyncio.to_thread(
                search_service.search_similar_from_embedding, embedding, slug
            )
            if embedding is not None
            else []
        )
        await usage_service.record_search(user_id)
        if analytics:
            await analytics.log(
                user_id,
                "search_completed",
                kind="similar",
                source_slug=slug,
                matches=len(matches),
            )
        query_vec = embedding.astype(float).tolist() if embedding is not None else None
        await status_msg.delete()
        await deliver_search_results(
            callback.message,
            bot,
            matches,
            search_service,
            user_id,
            similar_to=actress_name,
            reply_to_message_id=callback.message.message_id,
            query_embedding=query_vec,
        )
    except Exception as exc:
        logger.exception("Ошибка similar для user=%s slug=%s: %s", user_id, slug, exc)
        if analytics:
            await analytics.log(user_id, "search_failed", kind="similar", source_slug=slug)
        await status_msg.edit_text("Произошла ошибка. Попробуйте позже.")


@router.message(F.document)
async def handle_document(message: Message) -> None:
    if message.document and message.document.mime_type and message.document.mime_type.startswith(
        "image/"
    ):
        await message.answer(
            "Отправьте фото как <b>изображение</b>, не как файл.\n"
            "Или сожмите фото — Telegram пришлёт его как картинку.",
            parse_mode="HTML",
        )
        return
    await message.answer("Пришлите фотографию девушки для поиска.")


@router.message(F.text == BTN_HELP)
async def menu_help(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text == BTN_BALANCE)
async def menu_balance(message: Message, usage_service: UsageService) -> None:
    from bot.payment_handlers import cmd_balance

    await cmd_balance(message, usage_service)


@router.message(F.text == BTN_BUY)
async def menu_buy(
    message: Message,
    usage_service: UsageService,
    crypto_enabled: bool,
    stars_enabled: bool,
) -> None:
    from bot.payment_handlers import cmd_buy

    await cmd_buy(message, usage_service, crypto_enabled, stars_enabled)


@router.message()
async def handle_other(message: Message, usage_service: UsageService) -> None:
    if message.from_user:
        await usage_service.touch_user(message.from_user.id)
    await message.answer(
        "Нажмите <b>📷 Новое фото</b> в меню или просто пришлите изображение.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
