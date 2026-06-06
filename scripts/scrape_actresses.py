#!/usr/bin/env python3
"""
Сбор датасета фотографий порноактрис для Face Recognition.

Источники:
  - Babepedia (основной) — профили + галереи фото
  - ThePornDB (опционально) — REST API с метаданными

Использование:
  python scripts/scrape_actresses.py
  python scripts/scrape_actresses.py --source babepedia --max-pages 5
  python scripts/scrape_actresses.py --source babepedia --resume
  python scripts/scrape_actresses.py --dry-run --max-pages 1
  python scripts/scrape_actresses.py --enrich --extra 5   # +5 фото к уже скачанным
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tqdm import tqdm

# Корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers import BabepediaScraper, ThePornDBScraper
from scrapers.base import ActressProfile, download_image, save_metadata

load_dotenv(PROJECT_ROOT / ".env")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "scrape.log", encoding="utf-8"),
        ],
    )


def load_config(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_progress(progress_file: Path) -> set[str]:
    if not progress_file.exists():
        return set()
    return set(progress_file.read_text(encoding="utf-8").splitlines())


def save_progress(progress_file: Path, slug: str, done: set[str]) -> None:
    done.add(slug)
    progress_file.write_text("\n".join(sorted(done)), encoding="utf-8")


def count_existing_images(actress_dir: Path) -> int:
    if not actress_dir.exists():
        return 0
    return sum(
        1 for p in actress_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )


def download_actress_images(
    profile: ActressProfile,
    raw_dir: Path,
    scraper,
    config: dict,
    extra_images: int = 0,
) -> int:
    download_cfg = config["download"]
    max_images = download_cfg["max_images_per_actress"]
    timeout = download_cfg["timeout"]
    actress_dir = raw_dir / profile.slug
    existing = count_existing_images(actress_dir)

    if extra_images > 0:
        max_images = existing + extra_images
    elif existing >= max_images:
        return 0

    urls: list[str] = []
    if download_cfg["download_list_thumbnails"] and profile.thumbnail_url:
        urls.append(profile.thumbnail_url)
    if download_cfg["download_profile_images"]:
        urls.extend(profile.image_urls)

    seen: set[str] = set()
    new_downloaded = 0
    for idx, url in enumerate(urls):
        if url in seen:
            continue
        seen.add(url)
        if idx >= max_images:
            break

        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".webp" in url.lower():
            ext = ".webp"

        dest = actress_dir / f"{idx:03d}{ext}"
        if dest.exists():
            continue
        if download_image(url, dest, scraper.session, timeout):
            new_downloaded += 1

    return new_downloaded


def process_profile(
    list_entry: ActressProfile,
    scraper,
    config: dict,
    paths: dict,
    dry_run: bool,
    extra_images: int = 0,
) -> ActressProfile | None:
    filters = config["filters"]
    download_cfg = config["download"]

    if not dry_run and download_cfg["download_profile_images"]:
        profile = scraper.fetch_profile(list_entry.profile_url)
        if list_entry.thumbnail_url and not profile.thumbnail_url:
            profile.thumbnail_url = list_entry.thumbnail_url
    else:
        profile = list_entry

    if not profile.matches_career_filter(
        filters.get("min_career_start"),
        filters.get("max_career_end"),
    ):
        logging.info(
            "Пропуск %s — карьера %s–%s не попадает в фильтр",
            profile.name,
            profile.career_start,
            profile.career_end or "now",
        )
        return None

    if dry_run:
        logging.info(
            "[dry-run] %s | фото: %d | карьера: %s–%s",
            profile.name,
            len(profile.image_urls),
            profile.career_start,
            profile.career_end or ("active" if profile.career_active else "?"),
        )
        return profile

    metadata_dir = PROJECT_ROOT / paths["metadata"]
    save_metadata(profile, metadata_dir)

    raw_dir = PROJECT_ROOT / paths["raw_images"]
    count = download_actress_images(
        profile, raw_dir, scraper, config, extra_images=extra_images
    )
    if extra_images > 0:
        logging.info("Докачано %s: +%d фото", profile.name, count)
    else:
        logging.info("Сохранено %s: %d фото", profile.name, count)
    return profile


def run_enrich(args: argparse.Namespace, config: dict) -> int:
    """Докачать фото для актрис, уже лежащих в data/raw/."""
    paths = config["paths"]
    download_cfg = config["download"]
    raw_dir = PROJECT_ROOT / paths["raw_images"]
    metadata_dir = PROJECT_ROOT / paths["metadata"]

    scraper = BabepediaScraper(
        request_delay=download_cfg["request_delay"],
        timeout=download_cfg["timeout"],
    )

    actress_dirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    if args.limit:
        actress_dirs = actress_dirs[: args.limit]

    enriched = 0
    new_photos = 0

    for actress_dir in tqdm(actress_dirs, desc="Докачка"):
        slug = actress_dir.name
        meta_file = metadata_dir / f"{slug}.json"
        if not meta_file.exists():
            logging.warning("Нет метаданных для %s — пропуск", slug)
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        profile_url = meta.get("profile_url")
        if not profile_url:
            logging.warning("Нет profile_url для %s — пропуск", slug)
            continue

        try:
            profile = scraper.fetch_profile(profile_url)
            before = count_existing_images(actress_dir)
            result = process_profile(
                profile,
                scraper,
                config,
                paths,
                args.dry_run,
                extra_images=args.extra,
            )
            if result is None:
                continue
            after = count_existing_images(actress_dir)
            added = after - before
            if added > 0:
                enriched += 1
                new_photos += added
        except Exception as exc:
            logging.error("Ошибка при докачке %s: %s", slug, exc)

    logging.info(
        "Докачка завершена: %d актрис, +%d фото",
        enriched,
        new_photos,
    )
    return enriched


def run_babepedia(args: argparse.Namespace, config: dict) -> int:
    source_cfg = config["sources"]["babepedia"]
    paths = config["paths"]
    download_cfg = config["download"]

    scraper = BabepediaScraper(
        request_delay=download_cfg["request_delay"],
        timeout=download_cfg["timeout"],
    )

    progress_file = PROJECT_ROOT / paths["metadata"] / ".progress_babepedia.txt"
    done = load_progress(progress_file) if args.resume else set()

    list_urls = [source_cfg["list_url"], *source_cfg.get("extra_lists", [])]
    processed = 0
    skipped = 0

    for list_url in list_urls:
        for list_entry in scraper.iter_actress_list(list_url, max_pages=args.max_pages):
            if list_entry.slug in done:
                skipped += 1
                continue

            try:
                result = process_profile(
                    list_entry, scraper, config, paths, args.dry_run
                )
                if result is None:
                    skipped += 1
                else:
                    processed += 1
                    if not args.dry_run:
                        save_progress(progress_file, list_entry.slug, done)
            except Exception as exc:
                logging.error("Ошибка для %s: %s", list_entry.name, exc)

            if args.limit and processed >= args.limit:
                break

        if args.limit and processed >= args.limit:
            break

    logging.info(
        "Babepedia завершён: обработано %d, пропущено %d", processed, skipped
    )
    return processed


def run_tpdb(args: argparse.Namespace, config: dict) -> int:
    import os

    token = os.getenv("TPDB_API_TOKEN", "").strip()
    if not token:
        logging.error(
            "TPDB_API_TOKEN не задан. Создайте токен на https://theporndb.net/user/api-tokens"
        )
        return 0

    source_cfg = config["sources"]["theporndb"]
    paths = config["paths"]
    download_cfg = config["download"]

    scraper = ThePornDBScraper(
        api_token=token,
        api_base=source_cfg["api_base"],
        per_page=source_cfg["per_page"],
        request_delay=download_cfg["request_delay"],
        timeout=download_cfg["timeout"],
    )

    progress_file = PROJECT_ROOT / paths["metadata"] / ".progress_tpdb.txt"
    done = load_progress(progress_file) if args.resume else set()
    processed = 0

    for list_entry in tqdm(scraper.iter_actress_list(), desc="ThePornDB"):
        if list_entry.slug in done:
            continue
        if args.limit and processed >= args.limit:
            break

        try:
            result = process_profile(
                list_entry, scraper, config, paths, args.dry_run
            )
            if result is not None:
                processed += 1
                if not args.dry_run:
                    save_progress(progress_file, list_entry.slug, done)
        except Exception as exc:
            logging.error("Ошибка для %s: %s", list_entry.name, exc)

    logging.info("ThePornDB завершён: обработано %d", processed)
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сбор фотографий порноактрис для датасета Face Recognition"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.yaml",
        help="Путь к config.yaml",
    )
    parser.add_argument(
        "--source",
        choices=["babepedia", "theporndb", "all"],
        default="babepedia",
        help="Источник данных",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Ограничить число страниц списка (для теста)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Максимум актрис для обработки",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Продолжить с места остановки",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только парсинг метаданных, без скачивания",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Докачать фото для уже скачанных актрис (data/raw/)",
    )
    parser.add_argument(
        "--extra",
        type=int,
        default=5,
        help="Сколько доп. фото на актрису при --enrich (по умолчанию 5)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(PROJECT_ROOT / config["paths"]["logs"])

    logging.info("Конфиг: %s", args.config)

    if args.enrich:
        logging.info("Режим докачки: +%d фото на актрису", args.extra)
        total = run_enrich(args, config)
        summary_path = PROJECT_ROOT / config["paths"]["metadata"] / "dataset_summary.json"
        summary_path.write_text(
            json.dumps(
                {"enrich_extra": args.extra, "actresses_enriched": total},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logging.info("Итого обогащено актрис: %d", total)
        return

    logging.info(
        "Фильтр карьеры: с %s года",
        config["filters"].get("min_career_start", "без ограничений"),
    )

    total = 0
    sources = config["sources"]

    if args.source in ("babepedia", "all") and sources["babepedia"]["enabled"]:
        total += run_babepedia(args, config)

    if args.source in ("theporndb", "all") and sources["theporndb"]["enabled"]:
        total += run_tpdb(args, config)

    # Сводка датасета
    summary_path = PROJECT_ROOT / config["paths"]["metadata"] / "dataset_summary.json"
    summary = {
        "total_processed": total,
        "sources": args.source,
        "filters": config["filters"],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Итого обработано: %d. Сводка: %s", total, summary_path)


if __name__ == "__main__":
    main()
