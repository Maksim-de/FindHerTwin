"""Рассылка «актриса дня» + похожие."""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from bot.analytics import EventLogger
from bot.db import Database
from bot.results_ui import deliver_digest_results, to_stored
from face.search_service import ActressMatch, FaceSearchService

logger = logging.getLogger(__name__)


def pick_random_actress(search_service: FaceSearchService) -> ActressMatch | None:
    actresses = list(search_service.face_index.mapping.get("actresses", {}).keys())
    if not actresses:
        return None

    random.shuffle(actresses)
    entries = search_service.face_index.mapping.get("entries", [])

    for slug in actresses:
        face_num = None
        for entry in entries:
            if entry["slug"] != slug:
                continue
            face_num = Path(entry["face_path"]).stem.removeprefix("face_")
            break
        if face_num is None:
            continue
        if search_service.face_index.get_embedding_for_actress(slug, face_num) is None:
            continue
        name = search_service.get_actress_name(slug)
        return search_service.match_from_parts(
            rank=0,
            slug=slug,
            face_num=face_num,
            name=name,
            score=1.0,
        )
    return None


async def send_digest_to_user(
    bot: Bot,
    user_id: int,
    search_service: FaceSearchService,
    source: ActressMatch,
    matches: list[ActressMatch],
    analytics: EventLogger | None = None,
) -> bool:
    try:
        face_num = source.face_crop.stem.removeprefix("face_")
        embedding = await asyncio.to_thread(
            search_service.get_actress_embedding, source.slug, face_num
        )
        query_vec = embedding.astype(float).tolist() if embedding is not None else None
        await deliver_digest_results(
            bot,
            user_id,
            matches,
            to_stored(source),
            search_service,
            user_id,
            query_embedding=query_vec,
        )
        if analytics:
            await analytics.log(
                user_id,
                "digest_sent",
                source_slug=source.slug,
                matches=len(matches),
            )
        return True
    except TelegramForbiddenError:
        logger.info("Digest: user %s заблокировал бота", user_id)
        return False
    except TelegramBadRequest as exc:
        logger.warning("Digest: не отправлено user %s: %s", user_id, exc)
        return False


async def run_digest_scheduler(
    bot: Bot,
    db: Database,
    search_service: FaceSearchService,
    digest_cfg: dict,
    analytics: EventLogger | None = None,
) -> None:
    if not digest_cfg.get("enabled", False):
        logger.info("Digest-рассылка отключена")
        return

    interval_hours = float(digest_cfg.get("interval_hours", 24))
    check_minutes = int(digest_cfg.get("check_interval_minutes", 30))
    logger.info(
        "Digest-рассылка: каждые %s ч, проверка каждые %s мин",
        interval_hours,
        check_minutes,
    )

    while True:
        try:
            await asyncio.sleep(check_minutes * 60)
            if search_service.is_stub_dataset:
                continue

            user_ids = await asyncio.to_thread(db.get_users_due_for_digest, interval_hours)
            if not user_ids:
                continue

            source = await asyncio.to_thread(pick_random_actress, search_service)
            if source is None:
                logger.warning("Digest: не удалось выбрать актрису")
                continue

            face_num = source.face_crop.stem.removeprefix("face_")
            matches = await asyncio.to_thread(
                search_service.search_similar_to_actress,
                source.slug,
                face_num,
            )
            if not matches:
                logger.warning("Digest: нет похожих для %s", source.slug)
                continue

            logger.info(
                "Digest: %s — «%s», похожих %s, получателей %s",
                source.slug,
                source.name,
                len(matches),
                len(user_ids),
            )

            for user_id in user_ids:
                sent = await send_digest_to_user(
                    bot, user_id, search_service, source, matches, analytics
                )
                if sent:
                    await asyncio.to_thread(db.mark_digest_sent, user_id)
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info("Digest-рассылка остановлена")
            raise
        except Exception:
            logger.exception("Digest-рассылка: ошибка цикла")
