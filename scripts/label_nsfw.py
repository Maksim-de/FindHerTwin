#!/usr/bin/env python3
"""
Разметка NSFW для фото в data/raw/.

Использование:
  python scripts/label_nsfw.py
  python scripts/label_nsfw.py --limit 50
  python scripts/label_nsfw.py --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from face.nsfw import IMAGE_EXTENSIONS, NsfwClassifier, NsfwLabelStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="NSFW-разметка фото актрис")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--raw", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Лимит актрис")
    parser.add_argument("--force", action="store_true", help="Переразметить все фото")
    args = parser.parse_args()

    config = load_config(args.config)
    paths = config.get("paths", {})
    nsfw_cfg = config.get("nsfw", {})

    raw_dir = args.raw or PROJECT_ROOT / paths.get("raw_images", "data/raw")
    labels_path = PROJECT_ROOT / nsfw_cfg.get(
        "labels_file", "data/metadata/nsfw_labels.json"
    )
    min_score = nsfw_cfg.get("min_score", 0.4)
    batch_size = nsfw_cfg.get("batch_size", 8)

    store = NsfwLabelStore(labels_path)
    classifier = NsfwClassifier(min_score=min_score)

    actress_dirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    if args.limit:
        actress_dirs = actress_dirs[: args.limit]

    stats = {"safe": 0, "explicit": 0, "skipped": 0}

    for actress_dir in tqdm(actress_dirs, desc="NSFW"):
        slug = actress_dir.name
        images = sorted(
            p for p in actress_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            continue

        existing = store._data.get(slug, {})
        to_label = images if args.force else [p for p in images if p.name not in existing]
        if not to_label:
            stats["skipped"] += len(images)
            continue

        labels = dict(existing)
        for i in range(0, len(to_label), batch_size):
            batch = to_label[i : i + batch_size]
            batch_labels = classifier.classify_batch(batch)
            labels.update(batch_labels)
            for level in batch_labels.values():
                stats[level] = stats.get(level, 0) + 1

        store.set_actress_labels(slug, labels)

    store.save()

    summary = {
        "actresses": len(store._data),
        "safe": stats.get("safe", 0),
        "explicit": stats.get("explicit", 0),
        "skipped_files": stats["skipped"],
    }
    logger.info("Готово: %s", summary)
    logger.info("Файл разметки: %s", labels_path)


if __name__ == "__main__":
    main()
