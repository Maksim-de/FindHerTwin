#!/usr/bin/env python3
"""
Поиск top-N похожих актрис по загруженному фото.

Использование:
  python scripts/search.py --image photo.jpg
  python scripts/search.py --image photo.jpg --top 5
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import face.bootstrap  # noqa: F401, E402 — до torch/faiss

import numpy as np
from PIL import Image

from face.detector import FaceDetector, get_device
from face.encoder import FaceEncoder
from face.index_store import FaceIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def encode_query(image_path: Path, encoder: FaceEncoder, detector: FaceDetector) -> np.ndarray | None:
    with Image.open(image_path) as img:
        is_face_crop = img.size == (160, 160)

    if is_face_crop:
        return encoder.encode_crop_path(image_path)
    return encoder.encode_photo_path(image_path, detector)


def resolve_face_path(face_path: str) -> Path:
    path = Path(face_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def guess_raw_path(face_path: Path) -> Path | None:
    """face_003.jpg в processed → 003.jpg в raw (тот же индекс при сборке)."""
    slug = face_path.parent.name
    face_num = face_path.stem.removeprefix("face_")
    raw_dir = PROJECT_ROOT / "data" / "raw" / slug
    for ext in IMAGE_EXTENSIONS:
        candidate = raw_dir / f"{face_num}{ext}"
        if candidate.exists():
            return candidate
    return None


def format_result_paths(result) -> dict[str, str | None]:
    face_abs = resolve_face_path(result.face_path)
    raw_abs = guess_raw_path(face_abs)
    return {
        "face_crop": str(face_abs),
        "raw_photo": str(raw_abs) if raw_abs else None,
        "raw_folder": str(PROJECT_ROOT / "data" / "raw" / result.slug),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Поиск похожих актрис по фото")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--image", type=Path, required=True, help="Путь к фото")
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")
    args = parser.parse_args()

    config = load_config(args.config)
    paths = config.get("paths", {})
    face_cfg = config.get("face", {})

    index_dir = args.index_dir or PROJECT_ROOT / paths.get("index", "data/index")
    top_k = args.top or face_cfg.get("search_top_k", 5)
    min_prob = face_cfg.get("min_face_probability", 0.90)

    if not args.image.exists():
        logger.error("Файл не найден: %s", args.image)
        sys.exit(1)

    logger.info("Устройство: %s", get_device())

    # FAISS до torch — меньше шансов конфликта OpenMP на macOS
    face_index = FaceIndex(index_dir)
    face_index.load()

    detector = FaceDetector(min_probability=min_prob)
    encoder = FaceEncoder()

    embedding = encode_query(args.image, encoder, detector)
    if embedding is None:
        logger.error("Лицо не найдено на фото: %s", args.image)
        sys.exit(1)

    results = face_index.search(embedding, top_k=top_k)
    if not results:
        logger.warning("Совпадений не найдено")
        sys.exit(0)

    query_abs = args.image.resolve()
    logger.info("Запрос: %s", query_abs)

    if args.json:
        output = []
        for i, r in enumerate(results):
            paths = format_result_paths(r)
            output.append(
                {
                    "rank": i + 1,
                    "name": r.name,
                    "slug": r.slug,
                    "score": round(r.score, 4),
                    "face_path": paths["face_crop"],
                    "raw_photo": paths["raw_photo"],
                    "raw_folder": paths["raw_folder"],
                    "thumbnail": r.thumbnail,
                }
            )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    best = results[0]
    best_paths = format_result_paths(best)
    logger.info(
        "Наиболее похожая актриса: %s (score=%.4f)",
        best.name,
        best.score,
    )
    logger.info("Кроп лица: %s", best_paths["face_crop"])
    if best_paths["raw_photo"]:
        logger.info("Оригинал фото: %s", best_paths["raw_photo"])
    else:
        logger.info("Папка с фото актрисы: %s", best_paths["raw_folder"])

    print(f"\nTop-{top_k} похожих актрис для: {args.image.name}\n")
    print(f"{'#':<4} {'Score':<8} {'Имя':<28} {'Похожее фото'}")
    print("-" * 100)
    for i, r in enumerate(results, 1):
        paths = format_result_paths(r)
        photo_hint = paths["raw_photo"] or paths["face_crop"]
        print(f"{i:<4} {r.score:<8.4f} {r.name:<28} {photo_hint}")

    print(f"\nЛучшее совпадение — кроп: {best_paths['face_crop']}")
    if best_paths["raw_photo"]:
        print(f"Лучшее совпадение — оригинал: {best_paths['raw_photo']}")


if __name__ == "__main__":
    main()
