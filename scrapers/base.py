from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin

import cloudscraper
from lxml import html

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class ActressProfile:
    """Метаданные актрисы для датасета."""

    name: str
    source: str
    profile_url: str
    slug: str
    aliases: list[str] = field(default_factory=list)
    birthdate: str | None = None
    career_start: int | None = None
    career_end: int | None = None
    career_active: bool = False
    ethnicity: str | None = None
    country: str | None = None
    image_urls: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def matches_career_filter(
        self,
        min_start: int | None,
        max_end: int | None,
    ) -> bool:
        if min_start is None and max_end is None:
            return True
        if self.career_start is None:
            return True  # нет данных — не отбрасываем
        if min_start is not None and self.career_start < min_start:
            return False
        if max_end is not None:
            end_year = self.career_end or (2026 if self.career_active else self.career_start)
            if end_year > max_end:
                return False
        return True


class BaseScraper(ABC):
    def __init__(
        self,
        request_delay: float = 1.5,
        timeout: int = 30,
    ) -> None:
        self.request_delay = request_delay
        self.timeout = timeout
        self._last_request_at = 0.0
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False},
            delay=5,
        )
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        # Прогрев сессии — Babepedia отдаёт 403 без cookies
        try:
            self.session.get("https://www.babepedia.com/", timeout=timeout)
        except Exception:
            pass

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str, **kwargs) -> cloudscraper.CloudScraper:
        self._throttle()
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    @staticmethod
    def slugify(name: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", name.lower())
        return re.sub(r"[-\s]+", "_", slug).strip("_")

    @abstractmethod
    def iter_actress_list(self, list_url: str) -> Iterator[ActressProfile]:
        ...

    @abstractmethod
    def fetch_profile(self, profile_url: str) -> ActressProfile:
        ...


def save_metadata(profile: ActressProfile, metadata_dir: Path) -> Path:
    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / f"{profile.slug}.json"
    path.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def download_image(url: str, dest: Path, session: cloudscraper.CloudScraper, timeout: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return True
    try:
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        dest.write_bytes(response.content)
        return True
    except Exception as exc:
        logger.warning("Не удалось скачать %s: %s", url, exc)
        return False


def resolve_image_url(base_url: str, href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)


def parse_career_years(career_text: str) -> tuple[int | None, int | None, bool]:
    """
    Парсит строки вида '2015-Present', '2008 - 2019', '2010-'.
    """
    if not career_text:
        return None, None, False

    text = career_text.strip().split(" ", 1)[0]
    if "-" not in text:
        year_match = re.search(r"\d{4}", text)
        if year_match:
            year = int(year_match.group())
            return year, year, False
        return None, None, False

    start_str, end_str = text.split("-", 1)
    start_match = re.search(r"\d{4}", start_str)
    if not start_match:
        return None, None, False

    start_year = int(start_match.group())
    end_str = end_str.strip()
    if not end_str or end_str.lower() == "present":
        return start_year, None, True

    end_match = re.search(r"\d{4}", end_str)
    if end_match:
        return start_year, int(end_match.group()), False
    return start_year, None, True
