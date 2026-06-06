"""Структурированные события пользователей (JSONL для аналитики)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from aiogram.types import CallbackQuery, Message

from bot.menu import (
    BTN_BALANCE,
    BTN_BUY,
    BTN_HELP,
    BTN_NEW_PHOTO,
    CALLBACK_NEW_PHOTO,
)
from bot.results_ui import CALLBACK_NAV, CALLBACK_SIMILAR

logger = logging.getLogger(__name__)


class EventLogger:
    def __init__(self, events_path: Path, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.events_path = events_path
        self._lock = Lock()
        if enabled:
            events_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_sync(self, user_id: int, event: str, meta: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "event": event,
            **meta,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock, self.events_path.open("a", encoding="utf-8") as f:
            f.write(line)

    async def log(self, user_id: int, event: str, **meta: Any) -> None:
        if not self.enabled or not user_id:
            return
        try:
            await asyncio.to_thread(self._write_sync, user_id, event, meta)
        except Exception:
            logger.exception("Не удалось записать событие %s", event)


def classify_incoming(event: Message | CallbackQuery) -> tuple[int, str, dict[str, Any]] | None:
    user = event.from_user
    if user is None:
        return None
    user_id = user.id

    if isinstance(event, Message):
        if event.photo:
            return user_id, "photo_upload", {}
        if event.document:
            mime = event.document.mime_type or ""
            return user_id, "document_upload", {"mime": mime}
        text = (event.text or "").strip()
        if text.startswith("/"):
            cmd = text.split()[0].lstrip("/").split("@")[0]
            return user_id, "command", {"command": cmd}
        menu_map = {
            BTN_NEW_PHOTO: "menu_new_photo",
            BTN_BUY: "menu_buy",
            BTN_BALANCE: "menu_balance",
            BTN_HELP: "menu_help",
        }
        if text in menu_map:
            return user_id, menu_map[text], {}
        if text:
            return user_id, "text_message", {"preview": text[:40]}
        return user_id, "message_other", {}

    if not event.data:
        return user_id, "callback_empty", {}

    data = event.data
    if data.startswith(CALLBACK_NAV):
        rank = data.split(":")[-1]
        return user_id, "button_nav", {"rank": rank}
    if data.startswith(CALLBACK_SIMILAR):
        rank = data.split(":")[-1]
        return user_id, "button_similar", {"rank": rank}
    if data == CALLBACK_NEW_PHOTO:
        return user_id, "button_new_photo", {}
    if data.startswith("stars:"):
        return user_id, "button_buy_stars", {"product": data.split(":", 1)[-1]}
    if data.startswith("crypto:"):
        return user_id, "button_buy_crypto", {"product": data.split(":", 1)[-1]}
    if data.startswith("check_crypto:"):
        return user_id, "button_check_crypto", {}
    return user_id, "callback_other", {"data": data[:48]}
