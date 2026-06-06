#!/usr/bin/env python3
"""
Каталог лиц (mapping.json) без генерации embeddings.

Использование:
  python scripts/build_mapping.py
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

from face.mapping import build_mapping

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание mapping.json для индекса")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--processed", type=Path, default=None)
    parser.add_argument("--index-dir", type=Path, default=None)
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    paths = config.get("paths", {})

    processed_dir = args.processed or PROJECT_ROOT / paths.get("processed", "data/processed")
    index_dir = args.index_dir or PROJECT_ROOT / paths.get("index", "data/index")
    metadata_dir = PROJECT_ROOT / paths.get("metadata", "data/metadata")

    mapping = build_mapping(processed_dir, metadata_dir, PROJECT_ROOT)
    index_dir.mkdir(parents=True, exist_ok=True)

    mapping_path = index_dir / "mapping.json"
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "total_faces": mapping["total_faces"],
        "total_actresses": mapping["total_actresses"],
        "embedding_dim": mapping["embedding_dim"],
        "embeddings_ready": False,
        "faiss_ready": False,
    }
    (index_dir / "index_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Mapping готов: %d лиц, %d актрис → %s",
        mapping["total_faces"],
        mapping["total_actresses"],
        mapping_path,
    )
    logger.info("Следующий шаг: python scripts/generate_embeddings.py")


if __name__ == "__main__":
    main()
