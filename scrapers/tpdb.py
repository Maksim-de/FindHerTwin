from __future__ import annotations

import logging
from typing import Iterator

from scrapers.base import ActressProfile, BaseScraper, parse_career_years

logger = logging.getLogger(__name__)


class ThePornDBScraper(BaseScraper):
    """
    Парсер ThePornDB через публичный REST API (metadataapi.net).

    Требует API-токен: https://theporndb.net/user/api-tokens
    Документация: https://api.theporndb.net/docs
    """

    source_name = "theporndb"

    def __init__(
        self,
        api_token: str,
        api_base: str = "https://api.metadataapi.net",
        per_page: int = 100,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.api_base = api_base.rstrip("/")
        self.per_page = per_page
        self.session.headers["Authorization"] = f"Bearer {api_token}"
        self.session.headers["Accept"] = "application/json"

    def iter_actress_list(self, list_url: str = "") -> Iterator[ActressProfile]:
        page = 1

        while True:
            url = f"{self.api_base}/performers"
            params = {"page": page, "per_page": self.per_page}
            logger.info("ThePornDB API: страница %s", page)

            response = self.get(url, params=params)
            payload = response.json()

            data = payload.get("data", [])
            if not data:
                break

            for item in data:
                yield self._parse_performer(item)

            meta = payload.get("meta", {})
            pagination = meta.get("pagination", {})
            total_pages = pagination.get("total_pages")
            if total_pages is not None and page >= total_pages:
                break
            page += 1

    def fetch_profile(self, profile_url: str) -> ActressProfile:
        performer_id = profile_url.rstrip("/").split("/")[-1]
        url = f"{self.api_base}/performers/{performer_id}"
        response = self.get(url)
        return self._parse_performer(response.json().get("data", response.json()))

    def _parse_performer(self, item: dict) -> ActressProfile:
        extras = item.get("extras", {}) or {}
        name = item.get("name", "Unknown")
        performer_id = str(item.get("id", ""))

        profile = ActressProfile(
            name=name,
            source=self.source_name,
            profile_url=f"{self.api_base}/performers/{performer_id}",
            slug=self.slugify(name),
            aliases=item.get("aliases", []) or [],
            birthdate=extras.get("birthday"),
            ethnicity=extras.get("ethnicity"),
            country=extras.get("birthplace"),
        )

        career = extras.get("career_start_year") or extras.get("career")
        if isinstance(career, int):
            profile.career_start = career
        elif isinstance(career, str):
            start, end, active = parse_career_years(career)
            profile.career_start = start
            profile.career_end = end
            profile.career_active = active

        image = item.get("image") or item.get("face")
        if image:
            profile.image_urls.append(image)
            profile.thumbnail_url = image

        return profile
