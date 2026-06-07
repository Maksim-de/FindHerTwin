"""SQLite-хранилище пользователей, дневных лимитов и платежей."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock


@dataclass
class UserRecord:
    user_id: int
    credits: int
    unlimited_until: datetime | None


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    credits INTEGER NOT NULL DEFAULT 0,
                    unlimited_until TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_usage (
                    user_id INTEGER NOT NULL,
                    usage_date TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    product TEXT NOT NULL,
                    external_id TEXT NOT NULL UNIQUE,
                    amount TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                """
            )
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "last_digest_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_digest_at TEXT")
        if "language_code" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN language_code TEXT")

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_user_language(self, user_id: int) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT language_code FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            return row["language_code"]

    def set_user_language(self, user_id: int, language_code: str) -> None:
        self.ensure_user(user_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET language_code = ? WHERE user_id = ?",
                (language_code, user_id),
            )

    def ensure_user(self, user_id: int) -> UserRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, credits, unlimited_until FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO users (user_id, credits, unlimited_until, created_at) VALUES (?, 0, NULL, ?)",
                    (user_id, self._now_iso()),
                )
                return UserRecord(user_id=user_id, credits=0, unlimited_until=None)
            return UserRecord(
                user_id=row["user_id"],
                credits=row["credits"],
                unlimited_until=self._parse_dt(row["unlimited_until"]),
            )

    def get_daily_count(self, user_id: int, usage_date: str) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ).fetchone()
            return int(row["count"]) if row else 0

    def increment_daily(self, user_id: int, usage_date: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (user_id, usage_date, count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, usage_date) DO UPDATE SET count = count + 1
                """,
                (user_id, usage_date),
            )

    def use_credit(self, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT credits FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None or row["credits"] <= 0:
                return False
            conn.execute(
                "UPDATE users SET credits = credits - 1 WHERE user_id = ?",
                (user_id,),
            )
            return True

    def add_credits(self, user_id: int, amount: int) -> None:
        self.ensure_user(user_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET credits = credits + ? WHERE user_id = ?",
                (amount, user_id),
            )

    def extend_unlimited(self, user_id: int, days: int) -> datetime:
        self.ensure_user(user_id)
        now = datetime.now(timezone.utc)
        user = self.ensure_user(user_id)
        base = user.unlimited_until if user.unlimited_until and user.unlimited_until > now else now
        new_until = base.replace(microsecond=0) + timedelta(days=days)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET unlimited_until = ? WHERE user_id = ?",
                (new_until.isoformat(), user_id),
            )
        return new_until

    def create_payment(
        self,
        user_id: int,
        provider: str,
        product: str,
        external_id: str,
        amount: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO payments
                (user_id, provider, product, external_id, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (user_id, provider, product, external_id, amount, self._now_iso()),
            )

    def complete_payment(self, external_id: str) -> tuple[int, str] | None:
        """Возвращает (user_id, product) при первом подтверждении, иначе None."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, product, status FROM payments WHERE external_id = ?",
                (external_id,),
            ).fetchone()
            if row is None or row["status"] == "completed":
                return None
            conn.execute(
                """
                UPDATE payments
                SET status = 'completed', completed_at = ?
                WHERE external_id = ? AND status != 'completed'
                """,
                (self._now_iso(), external_id),
            )
            return int(row["user_id"]), str(row["product"])

    def get_users_due_for_digest(self, interval_hours: float) -> list[int]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=interval_hours)
        ).isoformat()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id FROM users
                WHERE last_digest_at IS NULL OR last_digest_at <= ?
                ORDER BY user_id
                """,
                (cutoff,),
            ).fetchall()
            return [int(row["user_id"]) for row in rows]

    def mark_digest_sent(self, user_id: int) -> None:
        self.ensure_user(user_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET last_digest_at = ? WHERE user_id = ?",
                (self._now_iso(), user_id),
            )

    def get_user_summary(self, user_id: int, usage_date: str, free_daily_limit: int) -> dict:
        user = self.ensure_user(user_id)
        daily_used = self.get_daily_count(user_id, usage_date)
        daily_left = max(0, free_daily_limit - daily_used)
        unlimited_active = bool(
            user.unlimited_until and user.unlimited_until > datetime.now(timezone.utc)
        )
        return {
            "credits": user.credits,
            "daily_used": daily_used,
            "daily_left": daily_left,
            "unlimited_active": unlimited_active,
            "unlimited_until": user.unlimited_until,
        }
