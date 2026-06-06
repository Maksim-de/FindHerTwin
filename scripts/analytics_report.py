#!/usr/bin/env python3
"""
Сводка по events.jsonl.

  python scripts/analytics_report.py
  python scripts/analytics_report.py --days 7
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVENTS = PROJECT_ROOT / "logs" / "events.jsonl"


def load_events(path: Path, days: int) -> list[dict]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = datetime.fromisoformat(row["ts"])
        if ts >= cutoff:
            events.append(row)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Аналитика бота из events.jsonl")
    parser.add_argument("--file", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--days", type=int, default=1, help="За сколько дней")
    args = parser.parse_args()

    events = load_events(args.file, args.days)
    if not events:
        print(f"Нет событий в {args.file} за {args.days} дн.")
        return

    users_all = {e["user_id"] for e in events}
    by_day_users: dict[str, set[int]] = defaultdict(set)
    by_day_events: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()

    for e in events:
        day = e["ts"][:10]
        by_day_users[day].add(e["user_id"])
        by_day_events[day] += 1
        event_counts[e["event"]] += 1

    print(f"Файл: {args.file}")
    print(f"Период: {args.days} дн., событий: {len(events)}")
    print(f"Уникальных пользователей: {len(users_all)}")
    print()

    print("Активные пользователи по дням (любое действие):")
    for day in sorted(by_day_users):
        print(f"  {day}: {len(by_day_users[day])} users, {by_day_events[day]} events")
    print()

    print("Топ событий:")
    for name, count in event_counts.most_common(15):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
