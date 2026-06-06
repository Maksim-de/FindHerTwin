#!/usr/bin/env python3
"""
Детекция лиц (MTCNN) и сохранение кропов 160×160 в data/processed/.

Использование:
  python scripts/prepare_dataset.py
  python scripts/prepare_dataset.py --input data/raw --output data/processed
  python scripts/prepare_dataset.py --limit 10          # только 10 актрис (сэмпл)
  python scripts/prepare_dataset.py --min-probability 0.85
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

import face.bootstrap  # noqa: F401, E402

from face.detector import FaceDetector, get_device

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def process_dataset(
    input_dir: Path,
    output_dir: Path,
    detector: FaceDetector,
    limit: int | None = None,
) -> dict:
    stats = {
        "input_images": 0,
        "faces_saved": 0,
        "no_face": 0,
        "actresses_with_faces": 0,
        "per_actress": {},
    }

    actress_dirs = sorted(p for p in input_dir.iterdir() if p.is_dir())
    if limit is not None:
        actress_dirs = actress_dirs[:limit]
    for actress_dir in tqdm(actress_dirs, desc="Актрисы"):
        slug = actress_dir.name
        images = sorted(
            p for p in actress_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            continue

        out_dir = output_dir / slug
        saved = 0
        no_face = 0

        for src in images:
            stats["input_images"] += 1
            crop = detector.crop_from_path(src)
            if crop is None:
                no_face += 1
                stats["no_face"] += 1
                continue

            dest = out_dir / f"face_{saved:03d}.jpg"
            detector.save_crop(crop, dest)
            saved += 1
            stats["faces_saved"] += 1

        if saved > 0:
            stats["actresses_with_faces"] += 1
            stats["per_actress"][slug] = {
                "faces": saved,
                "skipped": no_face,
                "total": len(images),
            }

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Подготовка кропов лиц для FaceNet")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--min-probability", type=float, default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Обработать только N первых актрис (для теста)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    paths = config.get("paths", {})
    face_cfg = config.get("face", {})

    input_dir = args.input or PROJECT_ROOT / paths.get("raw_images", "data/raw")
    output_dir = args.output or PROJECT_ROOT / paths.get("processed", "data/processed")
    min_prob = args.min_probability or face_cfg.get("min_face_probability", 0.90)

    logger.info("Устройство: %s", get_device())
    logger.info("Вход: %s → Выход: %s", input_dir, output_dir)
    if args.limit:
        logger.info("Сэмпл: только %d актрис", args.limit)

    detector = FaceDetector(min_probability=min_prob)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = process_dataset(input_dir, output_dir, detector, limit=args.limit)

    report_path = output_dir / "preparation_stats.json"
    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Готово: %d лиц из %d фото (%d актрис). Без лица: %d. Отчёт: %s",
        stats["faces_saved"],
        stats["input_images"],
        stats["actresses_with_faces"],
        stats["no_face"],
        report_path,
    )


if __name__ == "__main__":
    main()
