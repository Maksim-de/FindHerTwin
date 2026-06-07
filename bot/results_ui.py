"""UI карточки результатов: подпись, кнопки, отправка."""

from __future__ import annotations

import re

from aiogram import Bot
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from pathlib import Path

from bot.i18n import Lang, t
from bot.menu import CALLBACK_NEW_PHOTO
from bot.session_cache import SearchSession, SearchSessionCache, StoredMatch
from face.search_service import ActressMatch, FaceSearchService

CALLBACK_SIMILAR = "sim:"
CALLBACK_NAV = "nav:"
SESSION_ID_RE = re.compile(r"^[0-9a-f]{12}$")

session_cache = SearchSessionCache()


def _photo_for(
    search_service: FaceSearchService,
    match: ActressMatch,
    session: SearchSession | None = None,
) -> Path | None:
    query = session.query_embedding if session else None
    return search_service.best_photo_path(match, query_embedding=query)


def to_stored(match: ActressMatch) -> StoredMatch:
    return StoredMatch(
        rank=match.rank,
        slug=match.slug,
        face_num=match.face_crop.stem.removeprefix("face_"),
        name=match.name,
        score=match.score,
        profile_url=match.profile_url,
    )


def stored_to_match(search_service: FaceSearchService, stored: StoredMatch) -> ActressMatch:
    return search_service.match_from_parts(
        rank=stored.rank,
        slug=stored.slug,
        face_num=stored.face_num,
        name=stored.name,
        score=stored.score,
        profile_url=stored.profile_url,
    )


def session_to_matches(
    search_service: FaceSearchService, session: SearchSession
) -> list[ActressMatch]:
    return [stored_to_match(search_service, stored) for stored in session.matches]


def resolve_view(
    search_service: FaceSearchService, session: SearchSession, rank: int
) -> ActressMatch | None:
    stored = session.get_view(rank)
    if stored is None:
        return None
    match = stored_to_match(search_service, stored)
    if rank == 0:
        match.rank = 0
    return match


def results_keyboard(
    session_id: str,
    current_rank: int,
    total: int,
    *,
    has_source: bool,
    lang: Lang = "ru",
) -> InlineKeyboardMarkup:
    nav_row = [
        InlineKeyboardButton(
            text=f"• {rank} •" if rank == current_rank else str(rank),
            callback_data=f"{CALLBACK_NAV}{session_id}:{rank}",
        )
        for rank in range(1, total + 1)
    ]
    if has_source:
        nav_row.append(
            InlineKeyboardButton(
                text="• ⭐ •" if current_rank == 0 else t(lang, "btn_star_of_day"),
                callback_data=f"{CALLBACK_NAV}{session_id}:0",
            )
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav_row,
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_find_similar"),
                    callback_data=f"{CALLBACK_SIMILAR}{session_id}:{current_rank}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_new_photo_inline"),
                    callback_data=CALLBACK_NEW_PHOTO,
                )
            ],
        ]
    )


def format_caption(
    matches: list[ActressMatch],
    current_rank: int,
    *,
    similar_to: str | None = None,
    is_digest: bool = False,
    lang: Lang = "ru",
) -> str:
    lines: list[str] = []
    if is_digest and similar_to:
        lines.append(t(lang, "digest_title", name=similar_to))
        lines.append("")
    elif similar_to:
        lines.append(t(lang, "similar_to", name=similar_to))
        lines.append("")

    lines.append(t(lang, "top5_title"))
    for match in matches:
        lines.append(f"{match.rank}. {match.name} — {int(match.score * 100)}%")

    lines.append("")
    if current_rank == 0 and similar_to:
        lines.append(t(lang, "digest_star", name=similar_to))
    else:
        current = next((m for m in matches if m.rank == current_rank), matches[0])
        lines.append(
            t(
                lang,
                "match_line",
                rank=current.rank,
                name=current.name,
                score=int(current.score * 100),
            )
        )
    return "\n".join(lines)


def parse_session_callback(payload: str) -> tuple[str, int] | None:
    session_id, _, rank_str = payload.rpartition(":")
    if not SESSION_ID_RE.fullmatch(session_id) or not rank_str.isdigit():
        return None
    return session_id, int(rank_str)


async def _send_card(
    bot: Bot,
    chat_id: int,
    matches: list[ActressMatch],
    current: ActressMatch,
    current_rank: int,
    search_service: FaceSearchService,
    session_id: str,
    *,
    similar_to: str | None = None,
    is_digest: bool = False,
    has_source: bool = False,
    reply_to_message_id: int | None = None,
    session: SearchSession | None = None,
    lang: Lang = "ru",
) -> None:
    keyboard = results_keyboard(
        session_id, current_rank, len(matches), has_source=has_source, lang=lang
    )
    caption = format_caption(
        matches, current_rank, similar_to=similar_to, is_digest=is_digest, lang=lang
    )
    photo = _photo_for(search_service, current, session)

    if photo:
        await bot.send_photo(
            chat_id,
            FSInputFile(photo),
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
            reply_to_message_id=reply_to_message_id,
        )
        return

    caption += f"\n\n<i>{t(lang, 'no_safe_photo')}</i>"
    await bot.send_message(
        chat_id,
        caption,
        parse_mode="HTML",
        reply_markup=keyboard,
        reply_to_message_id=reply_to_message_id,
    )


async def send_match_card(
    message: Message,
    bot: Bot,
    matches: list[ActressMatch],
    current: ActressMatch,
    current_rank: int,
    search_service: FaceSearchService,
    session_id: str,
    *,
    similar_to: str | None = None,
    is_digest: bool = False,
    has_source: bool = False,
    reply_to_message_id: int | None = None,
    session: SearchSession | None = None,
    lang: Lang = "ru",
) -> None:
    await _send_card(
        bot,
        message.chat.id,
        matches,
        current,
        current_rank,
        search_service,
        session_id,
        similar_to=similar_to,
        is_digest=is_digest,
        has_source=has_source,
        reply_to_message_id=reply_to_message_id,
        session=session,
        lang=lang,
    )


async def update_match_card(
    bot: Bot,
    message: Message,
    matches: list[ActressMatch],
    current: ActressMatch,
    current_rank: int,
    search_service: FaceSearchService,
    session_id: str,
    session: SearchSession,
    lang: Lang = "ru",
) -> None:
    keyboard = results_keyboard(
        session_id,
        current_rank,
        len(matches),
        has_source=session.source is not None,
        lang=lang,
    )
    caption = format_caption(
        matches,
        current_rank,
        similar_to=session.similar_to,
        is_digest=session.is_digest,
        lang=lang,
    )
    photo = _photo_for(search_service, current, session)

    if message.photo and photo:
        await bot.edit_message_media(
            chat_id=message.chat.id,
            message_id=message.message_id,
            media=InputMediaPhoto(media=FSInputFile(photo), caption=caption, parse_mode="HTML"),
            reply_markup=keyboard,
        )
        return

    if message.photo and not photo:
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption + f"\n\n<i>{t(lang, 'no_safe_photo')}</i>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    text = caption + (
        f"\n\n<i>{t(lang, 'no_safe_photo')}</i>" if not photo else ""
    )
    if photo:
        await message.delete()
        await bot.send_photo(
            message.chat.id,
            FSInputFile(photo),
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def deliver_search_results(
    message: Message,
    bot: Bot,
    matches: list[ActressMatch],
    search_service: FaceSearchService,
    user_id: int,
    *,
    similar_to: str | None = None,
    source: StoredMatch | None = None,
    is_digest: bool = False,
    reply_to_message_id: int | None = None,
    query_embedding: list[float] | None = None,
    lang: Lang = "ru",
) -> None:
    if not matches:
        await message.answer(
            t(lang, "no_face"),
            reply_to_message_id=reply_to_message_id,
        )
        return

    session_id = session_cache.create(
        user_id,
        [to_stored(m) for m in matches],
        similar_to=similar_to,
        source=source,
        is_digest=is_digest,
        query_embedding=query_embedding,
    )
    session = session_cache.get(session_id, user_id)
    await send_match_card(
        message,
        bot,
        matches,
        matches[0],
        matches[0].rank,
        search_service,
        session_id,
        similar_to=similar_to,
        is_digest=is_digest,
        has_source=source is not None,
        reply_to_message_id=reply_to_message_id,
        session=session,
        lang=lang,
    )


async def deliver_digest_results(
    bot: Bot,
    chat_id: int,
    matches: list[ActressMatch],
    source: StoredMatch,
    search_service: FaceSearchService,
    user_id: int,
    query_embedding: list[float] | None = None,
    lang: Lang = "ru",
) -> None:
    if not matches:
        return

    session_id = session_cache.create(
        user_id,
        [to_stored(m) for m in matches],
        similar_to=source.name,
        source=source,
        is_digest=True,
        query_embedding=query_embedding,
    )
    session = session_cache.get(session_id, user_id)
    await _send_card(
        bot,
        chat_id,
        matches,
        matches[0],
        1,
        search_service,
        session_id,
        similar_to=source.name,
        is_digest=True,
        has_source=True,
        session=session,
        lang=lang,
    )
