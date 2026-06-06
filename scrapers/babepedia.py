from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Iterator
from urllib.parse import urljoin, urlparse

from lxml import html

from scrapers.base import (
    ActressProfile,
    BaseScraper,
    parse_career_years,
    resolve_image_url,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.babepedia.com"


class BabepediaScraper(BaseScraper):
    """
    Парсер Babepedia — основной источник фото и метаданных.

    ~17 000 порноактрис в списке pornstartop100.
    Профили: https://www.babepedia.com/babe/{Name_With_Underscores}
    """

    source_name = "babepedia"

    def iter_actress_list(
        self,
        list_url: str,
        max_pages: int | None = None,
    ) -> Iterator[ActressProfile]:
        page = 1
        total_pages = None

        while True:
            if max_pages is not None and page > max_pages:
                break
            page_url = list_url if page == 1 else f"{list_url}?page={page}"
            logger.info("Список Babepedia: страница %s — %s", page, page_url)

            response = self.get(page_url)
            tree = html.fromstring(response.text)
            self._ensure_valid_list_page(tree, page_url)

            if total_pages is None:
                total_pages = self._extract_total_pages(tree)
                logger.info("Всего страниц в списке: %s", total_pages)

            entries = self._parse_list_page(tree, list_url)
            if not entries:
                break

            yield from entries

            if total_pages is not None and page >= total_pages:
                break
            page += 1

    def _ensure_valid_list_page(self, tree: html.HtmlElement, page_url: str) -> None:
        title = (tree.xpath("//title/text()") or [""])[0].lower()
        blocked_markers = (
            "age verification",
            "access restricted",
            "just a moment",
            "attention required",
        )
        if any(marker in title for marker in blocked_markers):
            raise RuntimeError(
                f"Babepedia заблокировал доступ ({title!r}). "
                "Попробуйте VPN или увеличьте request_delay в config.yaml."
            )
        if not tree.xpath('//div[@class="thumbtext"]//a[contains(@href, "/babe/")]'):
            raise RuntimeError(
                f"Не удалось распарсить список актрис: {page_url}. "
                "Возможна геоблокировка или изменилась вёрстка сайта."
            )

    def _extract_total_pages(self, tree: html.HtmlElement) -> int | None:
        # "Showing page 1 of 172"
        headers = tree.xpath(
            '//*[contains(text(), "Showing page")]/text()'
        )
        for header in headers:
            match = re.search(r"page \d+ of (\d+)", header)
            if match:
                return int(match.group(1))
        return None

    def _parse_list_page(self, tree: html.HtmlElement, list_url: str) -> list[ActressProfile]:
        profiles: list[ActressProfile] = []
        seen_urls: set[str] = set()

        # Только основной список (div.thumbtext), без сайдбара и рекламы
        name_links = tree.xpath(
            '//div[@class="thumbtext"]//a[contains(@href, "/babe/")]'
        )
        thumb_by_href: dict[str, str] = {}
        for shot_link in tree.xpath(
            '//span[@class="thumbshot"]//a[contains(@href, "/babe/")]'
        ):
            href = shot_link.get("href", "")
            imgs = shot_link.xpath(".//img/@src")
            if href and imgs:
                thumb_by_href[href] = resolve_image_url(BASE_URL, imgs[0])

        for link in name_links:
            href = link.get("href", "")
            if not href or href in seen_urls:
                continue

            full_url = resolve_image_url(BASE_URL, href)
            parsed = urlparse(full_url)
            url_slug = parsed.path.split("/babe/", 1)[-1].strip("/")
            if not url_slug:
                continue

            name = (link.text_content() or "").strip()
            if not name:
                continue

            seen_urls.add(href)
            profiles.append(
                ActressProfile(
                    name=name,
                    source=self.source_name,
                    profile_url=full_url,
                    slug=self.slugify(url_slug),
                    thumbnail_url=thumb_by_href.get(href),
                )
            )

        return profiles

    def fetch_profile(self, profile_url: str) -> ActressProfile:
        response = self.get(profile_url)
        tree = html.fromstring(response.text)

        url_slug = urlparse(profile_url).path.split("/babe/", 1)[-1].strip("/")

        name_elem = tree.xpath('//h1[@id="babename"]')
        name = name_elem[0].text_content().strip() if name_elem else url_slug.replace("_", " ")

        profile = ActressProfile(
            name=name,
            source=self.source_name,
            profile_url=profile_url,
            slug=self.slugify(url_slug),
        )

        # Алиасы
        aliases = tree.xpath('//h2[@id="aka"][1]/text()')
        if aliases:
            profile.aliases = [
                alias.strip()
                for alias in aliases[0].strip().split(" - ")
                if alias.strip()
            ]

        # Дата рождения
        birth_container = tree.xpath(
            '//span[contains(text(), "Born:")]/following-sibling::span/a'
        )
        if birth_container:
            if len(birth_container) == 2:
                birth_text = " ".join(
                    node.text_content().strip() for node in birth_container
                )
                clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", birth_text)
                try:
                    birthdate = datetime.strptime(clean, "%d of %B %Y").date()
                    profile.birthdate = birthdate.isoformat()
                except ValueError:
                    pass
            elif len(birth_container) == 1:
                profile.birthdate = birth_container[0].text_content().strip()

        # Карьера
        career = self._biography_field(tree, "Years active", "")
        if not career:
            career_elems = tree.xpath(
                '//span[contains(text(), "Years active")]/following-sibling::span//text()'
            )
            career = career_elems[0].strip() if career_elems else None
        if career:
            start, end, active = parse_career_years(career)
            profile.career_start = start
            profile.career_end = end
            profile.career_active = active

        # Национальность
        flags = tree.xpath(
            '//span[contains(text(), "Nationality")]/following-sibling::span'
            '//span[contains(@class, "fi-")]/@class'
        )
        if flags:
            match = re.search(r"fi fi-([a-z]{2})", flags[0])
            if match:
                profile.country = match.group(1).upper()

        # Этничность
        ethnicity = self._biography_field(tree, "Ethnicity", "/a")
        if ethnicity:
            profile.ethnicity = ethnicity

        # Фото из галереи профиля
        main_imgs = tree.xpath('//div[@id="profbox2"]//a[@class="img"]/@href')
        user_imgs = tree.xpath(
            '//div[contains(@class,"useruploads2")]//a[@class="img"]/@href'
        )
        for href in main_imgs + user_imgs:
            url = resolve_image_url(BASE_URL, href)
            if url not in profile.image_urls:
                profile.image_urls.append(url)

        return profile

    @staticmethod
    def _biography_field(tree: html.HtmlElement, label: str, suffix: str) -> str | None:
        elems = tree.xpath(
            f'//span[contains(text(), "{label}")]/following-sibling::span{suffix}/text()'
        )
        return elems[0].strip() if elems else None

    def search_by_name(self, name: str) -> list[dict]:
        """Поиск через ajax-search.php (как в Stash CommunityScrapers)."""
        search_name = name.replace("-", " ")
        response = self.get(
            f"{BASE_URL}/ajax-search.php",
            params={"term": search_name},
        )
        return response.json()
