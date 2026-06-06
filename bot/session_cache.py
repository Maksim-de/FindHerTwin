"""Краткоживущий кэш результатов поиска для кнопок 1–5."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field


@dataclass
class StoredMatch:
    rank: int
    slug: str
    face_num: str
    name: str
    score: float
    profile_url: str | None


@dataclass
class SearchSession:
    user_id: int
    matches: list[StoredMatch]
    similar_to: str | None = None
    source: StoredMatch | None = None
    is_digest: bool = False
    query_embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)

    def get_match(self, rank: int) -> StoredMatch | None:
        for match in self.matches:
            if match.rank == rank:
                return match
        return None

    def get_view(self, rank: int) -> StoredMatch | None:
        if rank == 0:
            return self.source
        return self.get_match(rank)


class SearchSessionCache:
    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 5000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, SearchSession] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.created_at > self.ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

        if len(self._sessions) > self.max_sessions:
            oldest = sorted(
                self._sessions.items(), key=lambda item: item[1].created_at
            )
            for sid, _ in oldest[: len(self._sessions) - self.max_sessions]:
                del self._sessions[sid]

    def create(
        self,
        user_id: int,
        matches: list[StoredMatch],
        similar_to: str | None = None,
        source: StoredMatch | None = None,
        is_digest: bool = False,
        query_embedding: list[float] | None = None,
    ) -> str:
        self._cleanup()
        session_id = secrets.token_hex(6)
        self._sessions[session_id] = SearchSession(
            user_id=user_id,
            matches=matches,
            similar_to=similar_to,
            source=source,
            is_digest=is_digest,
            query_embedding=query_embedding,
        )
        return session_id

    def get(self, session_id: str, user_id: int) -> SearchSession | None:
        self._cleanup()
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session
