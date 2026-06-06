#!/usr/bin/env python3
"""
Генерация FaceNet embeddings по mapping.json (тяжёлый шаг).

Использование:
  python scripts/generate_embeddings.py
  python scripts/generate_embeddings.py --limit 100
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import yaml
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import face.bootstrap  # noqa: F401, E402

from face.encoder import FaceEncoder, get_device
from face.mapping import EMBEDDING_DIM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерация FaceNet embeddings")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Только N первых лиц")
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    paths = config.get("paths", {})

    index_dir = args.index_dir or PROJECT_ROOT / paths.get("index", "data/index")
    mapping_path = index_dir / "mapping.json"
    if not mapping_path.exists():
        logger.error("mapping.json не найден. Сначала: python scripts/build_mapping.py")
        sys.exit(1)

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    entries = mapping["entries"]
    if args.limit:
        entries = entries[: args.limit]

    encoder = FaceEncoder()
    logger.info("Устройство: %s", get_device())
    logger.info("Лиц для обработки: %d", len(entries))

    vectors = np.zeros((len(entries), EMBEDDING_DIM), dtype=np.float32)
    failed = 0

    for i, entry in enumerate(tqdm(entries, desc="Embeddings")):
        face_path = PROJECT_ROOT / entry["face_path"]
        embedding = encoder.encode_crop_path(face_path)
        if embedding is None:
            failed += 1
            continue
        vectors[i] = embedding
        entry["has_embedding"] = True

    embeddings_path = index_dir / "embeddings.npy"
    np.save(embeddings_path, vectors)

    mapping["embeddings_ready"] = failed == 0
    mapping["embeddings_failed"] = failed
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_path = index_dir / "index_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.update(
        {
            "total_faces": mapping["total_faces"],
            "total_actresses": mapping["total_actresses"],
            "embeddings_ready": mapping["embeddings_ready"],
            "embeddings_failed": failed,
            "embeddings_file": str(embeddings_path.name),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Embeddings сохранены: %s (%d векторов, ошибок: %d)",
        embeddings_path,
        len(entries),
        failed,
    )
    logger.info("Следующий шаг: python scripts/build_index.py")


if __name__ == "__main__":
    main()
