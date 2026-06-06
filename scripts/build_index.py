#!/usr/bin/env python3
"""
Построение FAISS-индекса из готовых embeddings.npy + mapping.json.
Без генерации embeddings — для этого есть generate_embeddings.py.

Использование:
  python scripts/build_index.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# До faiss/torch: только faiss, без загрузки PyTorch через face.__init__
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from face.index_store import FaceIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Построение FAISS-индекса")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--index-dir", type=Path, default=None)
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    paths = config.get("paths", {})

    index_dir = args.index_dir or PROJECT_ROOT / paths.get("index", "data/index")
    mapping_path = index_dir / "mapping.json"
    embeddings_path = index_dir / "embeddings.npy"

    if not mapping_path.exists():
        logger.error("mapping.json не найден. Сначала: python scripts/build_mapping.py")
        sys.exit(1)
    if not embeddings_path.exists():
        logger.error(
            "embeddings.npy не найден. Сначала: python scripts/generate_embeddings.py"
        )
        sys.exit(1)

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    embeddings = np.load(embeddings_path)

    if embeddings.shape[0] != mapping["total_faces"]:
        logger.error(
            "Размер embeddings (%d) не совпадает с mapping (%d)",
            embeddings.shape[0],
            mapping["total_faces"],
        )
        sys.exit(1)

    face_index = FaceIndex(index_dir)
    face_index.build(embeddings, mapping)

    mapping["faiss_ready"] = True
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "total_faces": mapping["total_faces"],
        "total_actresses": mapping["total_actresses"],
        "embedding_dim": mapping["embedding_dim"],
        "embeddings_ready": True,
        "faiss_ready": True,
    }
    (index_dir / "index_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "FAISS-индекс готов: %d лиц, %d актрис → %s",
        mapping["total_faces"],
        mapping["total_actresses"],
        index_dir,
    )


if __name__ == "__main__":
    main()
