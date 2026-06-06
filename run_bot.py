#!/usr/bin/env python3
"""Точка входа для Amvera: монтирует /data, при необходимости ставит заглушку, запускает бота."""

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
logger = logging.getLogger(__name__)


def _link(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        return
    link.symlink_to(target)


def _is_real_index(index_dir: Path) -> bool:
    mapping_path = index_dir / "mapping.json"
    if not mapping_path.is_file():
        return False
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return not mapping.get("stub", False)


def seed_stub_dataset() -> bool:
    """Копирует минимальный индекс в /data, если реальный датасет ещё не загружен."""
    data_root = Path("/data")
    index_dir = data_root / "index"

    if _is_real_index(index_dir):
        return False

    if (index_dir / "mapping.json").is_file():
        logger.warning("Индекс в /data помечен как stub — ждём загрузку полного датасета")

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


def setup_data_mount() -> None:
    os.chdir(ROOT)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    for name in ("raw", "processed", "index", "metadata"):
        Path(f"/data/{name}").mkdir(parents=True, exist_ok=True)

    seed_stub_dataset()

    for name in ("raw", "processed", "index", "metadata"):
        _link(Path(f"/data/{name}"), ROOT / "data" / name)

    if Path("/data/bot.db").is_file():
        _link(Path("/data/bot.db"), ROOT / "data" / "bot.db")

    nsfw = Path("/data/metadata/nsfw_labels.json")
    if nsfw.is_file():
        _link(Path("/data/metadata/nsfw_labels.json"), ROOT / "data" / "metadata" / "nsfw_labels.json")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    setup_data_mount()
    raise SystemExit(subprocess.call([sys.executable, "-m", "bot.main"], cwd=ROOT))


if __name__ == "__main__":
    main()
