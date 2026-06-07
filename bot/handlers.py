from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.analytics import EventLogger
from bot.callback_utils import safe_callback_answer
from bot.i18n import Lang, help_text_bilingual, t
from bot.menu import (
    BTN_BALANCE_ALL,
    BTN_BUY_ALL,
    BTN_HELP_ALL,
    BTN_NEW_PHOTO_ALL,
    CALLBACK_NEW_PHOTO,
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
from face.dataset_status import describe_dataset
from face.search_service import FaceSearchService

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

router = Router()


def _welcome_text(lang: Lang, usage_service: UsageService) -> str:
    pack = usage_service.products["pack_15"]
    unlimited = usage_service.localized_product("unlimited", lang)
    limits_line = (
        t(lang, "welcome_limits_free", limit=usage_service.free_daily_limit)
        if usage_service.limits_enabled
        else t(lang, "welcome_limits_off")
    )
    return (
        f"{t(lang, 'welcome_intro')}\n\n"
        f"{limits_line}\n"
        f"{t(lang, 'welcome_pack', credits=pack.credits, price=pack.usdt_amount)}\n"
        f"{t(lang, 'welcome_unlimited', title=unlimited.title, price=unlimited.usdt_amount)}\n\n"
        f"{t(lang, 'welcome_footer')}"
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    usage_service: UsageService,
    lang: Lang,
    welcome_photo: Path | None = None,
) -> None:
    text = _welcome_text(lang, usage_service)
    keyboard = main_menu_keyboard(lang)

    if welcome_photo and welcome_photo.exists():
        await message.answer_photo(
            FSInputFile(welcome_photo),
            caption=text,
            reply_markup=keyboard,
        )
        return

    await message.answer(text, reply_markup=keyboard)


@router.message(Command("dataset"))
async def cmd_dataset(message: Message, search_service: FaceSearchService, lang: Lang) -> None:
    status = describe_dataset(search_service.data_root, project_root=PROJECT_ROOT)
    mode = t(lang, "dataset_stub") if search_service.is_stub_dataset else t(lang, "dataset_ready")
    await message.answer(
        f"<b>{t(lang, 'dataset_status_title')}:</b> {mode}\n\n<code>{status}</code>",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, lang: Lang) -> None:
    await message.answer(
        help_text_bilingual(),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(Command("search"))
async def cmd_search(message: Message, lang: Lang) -> None:
    await message.answer(
        t(lang, "new_photo_prompt"),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(F.text.in_(BTN_NEW_PHOTO_ALL))
async def menu_new_photo(message: Message, lang: Lang) -> None:
    await message.answer(
        t(lang, "new_photo_prompt"),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )


@router.callback_query(F.data == CALLBACK_NEW_PHOTO)
async def inline_new_photo(callback: CallbackQuery, lang: Lang) -> None:
    if callback.message:
        await callback.message.answer(
            t(lang, "new_photo_prompt"),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(lang),
        )
    await callback.answer()


@router.message(F.photo)
async def handle_photo(
    message: Message,
    bot: Bot,
    search_service: FaceSearchService,
    usage_service: UsageService,
    lang: Lang,
    temp_dir: Path,
    analytics: EventLogger | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else 0

    allowed, reason = await usage_service.can_search(user_id, lang)
    if not allowed:
        if analytics:
            await analytics.log(user_id, "limit_denied", action="photo_search")
        await message.answer(reason or t(lang, "limit_fallback"), parse_mode="HTML")
        return

    if search_service.is_stub_dataset:
        await message.answer(t(lang, "stub_dataset"), parse_mode="HTML")
        return

    status_msg = await message.answer(t(lang, "analyzing"))

    photo = message.photo[-1]
    temp_path = temp_dir / f"{user_id}_{photo.file_id}.jpg"

    try:
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            await status_msg.edit_text(t(lang, "download_failed"))
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
            lang=lang,
        )
    except Exception as exc:
        logger.exception("Ошибка поиска для user=%s: %s", user_id, exc)
        if analytics:
            await analytics.log(user_id, "search_failed", kind="photo")
        await status_msg.edit_text(t(lang, "search_error"))
    finally:
        temp_path.unlink(missing_ok=True)


@router.callback_query(F.data.startswith(CALLBACK_NAV))
async def handle_nav(
    callback: CallbackQuery,
    bot: Bot,
    search_service: FaceSearchService,
    lang: Lang,
) -> None:
    if not callback.message or not callback.from_user or not callback.data:
        await safe_callback_answer(callback)
        return

    parsed = parse_session_callback(callback.data.removeprefix(CALLBACK_NAV))
    if parsed is None:
        await safe_callback_answer(callback, t(lang, "stale_button"), show_alert=True)
        return

    session_id, rank = parsed
    session = session_cache.get(session_id, callback.from_user.id)
    if session is None:
        await safe_callback_answer(
            callback,
            t(lang, "session_expired"),
            show_alert=True,
        )
        return

    current = resolve_view(search_service, session, rank)
    if current is None:
        await safe_callback_answer(callback, t(lang, "no_such_rank"), show_alert=True)
        return

    await safe_callback_answer(callback)

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
            lang=lang,
        )
    except Exception as exc:
        logger.exception("Ошибка nav rank=%s: %s", rank, exc)
        await callback.message.answer(t(lang, "update_photo_failed"))


@router.callback_query(F.data.startswith(CALLBACK_SIMILAR))
async def handle_similar(
    callback: CallbackQuery,
    bot: Bot,
    search_service: FaceSearchService,
    usage_service: UsageService,
    lang: Lang,
    analytics: EventLogger | None = None,
) -> None:
    if not callback.message or not callback.from_user or not callback.data:
        await safe_callback_answer(callback)
        return

    user_id = callback.from_user.id
    allowed, reason = await usage_service.can_search(user_id, lang)
    if not allowed:
        if analytics:
            await analytics.log(user_id, "limit_denied", action="similar")
        await safe_callback_answer(
            callback, reason or t(lang, "limit_fallback"), show_alert=True
        )
        return

    if search_service.is_stub_dataset:
        await safe_callback_answer(callback, t(lang, "dataset_not_loaded"), show_alert=True)
        return

    payload = callback.data.removeprefix(CALLBACK_SIMILAR)
    parsed = parse_session_callback(payload)
    if parsed is not None:
        session_id, rank = parsed
        session = session_cache.get(session_id, user_id)
        if session is None:
            await safe_callback_answer(
                callback,
                t(lang, "session_expired"),
                show_alert=True,
            )
            return
        stored = session.get_view(rank)
        if stored is None:
            await safe_callback_answer(callback, t(lang, "no_such_rank"), show_alert=True)
            return
        slug = stored.slug
        face_num = stored.face_num
        actress_name = stored.name
    else:
        slug, _, face_num = payload.rpartition(":")
        if not slug:
            await safe_callback_answer(callback, t(lang, "bad_payload"), show_alert=True)
            return
        actress_name = search_service.get_actress_name(slug)

    await safe_callback_answer(callback)
    status_msg = await callback.message.answer(
        t(lang, "similar_search", name=actress_name),
        parse_mode="HTML",
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
            lang=lang,
        )
    except Exception as exc:
        logger.exception("Ошибка similar для user=%s slug=%s: %s", user_id, slug, exc)
        if analytics:
            await analytics.log(user_id, "search_failed", kind="similar", source_slug=slug)
        await status_msg.edit_text(t(lang, "similar_error"))


@router.message(F.document)
async def handle_document(message: Message, lang: Lang) -> None:
    if message.document and message.document.mime_type and message.document.mime_type.startswith(
        "image/"
    ):
        await message.answer(t(lang, "send_as_image"), parse_mode="HTML")
        return
    await message.answer(t(lang, "send_photo_prompt"))


@router.message(F.text.in_(BTN_HELP_ALL))
async def menu_help(message: Message, lang: Lang) -> None:
    await cmd_help(message, lang)


@router.message(F.text.in_(BTN_BALANCE_ALL))
async def menu_balance(message: Message, usage_service: UsageService, lang: Lang) -> None:
    from bot.payment_handlers import cmd_balance

    await cmd_balance(message, usage_service, lang)


@router.message(F.text.in_(BTN_BUY_ALL))
async def menu_buy(
    message: Message,
    usage_service: UsageService,
    lang: Lang,
    crypto_enabled: bool,
    stars_enabled: bool,
) -> None:
    from bot.payment_handlers import cmd_buy

    await cmd_buy(message, usage_service, crypto_enabled, stars_enabled, lang)


@router.message()
async def handle_other(message: Message, lang: Lang) -> None:
    await message.answer(
        t(lang, "fallback_hint"),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )
