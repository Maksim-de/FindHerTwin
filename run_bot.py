#!/usr/bin/env python3
"""Точка входа для Amvera: ставит заглушку датасета при необходимости и запускает бота."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
logger = logging.getLogger(__name__)


def _is_real_index(index_dir: Path) -> bool:
    mapping_path = index_dir / "mapping.json"
    if not mapping_path.is_file():
        return False
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return not mapping.get("stub", False)


def seed_stub_dataset(data_root: Path) -> bool:
    """Копирует минимальный индекс, если реальный датасет ещё не загружен."""
    index_dir = data_root / "index"

    if _is_real_index(index_dir):
        return False

    if (index_dir / "mapping.json").is_file():
        logger.warning("Индекс помечен как stub — ждём загрузку полного датасета в Amvera Data")

    bootstrap = ROOT / "bootstrap_data"
    if bootstrap.is_dir():
        for name in ("index", "metadata", "raw", "processed"):
            src = bootstrap / name
            if not src.exists():
                continue
            dest = data_root / name
            dest.mkdir(parents=True, exist_ok=True)
            for item in src.iterdir():
                target = dest / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)

    index_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = index_dir / "embeddings.npy"
    if not embeddings_path.is_file():
        np.save(embeddings_path, np.zeros((1, 512), dtype=np.float32))

    face_path = data_root / "processed" / "demo" / "face_000.jpg"
    if not face_path.is_file():
        face_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 160), color=(96, 96, 96)).save(face_path, quality=85)

    logger.warning(
        "Активна заглушка датасета. Загрузите index/raw/processed/metadata в Amvera Data и перезапустите бот."
    )
    return True


def setup_data_dirs() -> None:
    os.chdir(ROOT)
    (ROOT / "logs").mkdir(exist_ok=True)
    for name in ("raw", "processed", "index", "metadata"):
        (DATA_ROOT / name).mkdir(parents=True, exist_ok=True)
    seed_stub_dataset(DATA_ROOT)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    setup_data_dirs()
    raise SystemExit(subprocess.call([sys.executable, "-m", "bot.main"], cwd=ROOT))


if __name__ == "__main__":
    main()
