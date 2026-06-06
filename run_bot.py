#!/usr/bin/env python3
"""Точка входа для Amvera: монтирует /data и запускает бота."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _link(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        return
    link.symlink_to(target)


def setup_data_mount() -> None:
    os.chdir(ROOT)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    for name in ("raw", "processed", "index", "metadata"):
        Path(f"/data/{name}").mkdir(parents=True, exist_ok=True)
        _link(Path(f"/data/{name}"), ROOT / "data" / name)

    if Path("/data/bot.db").is_file():
        _link(Path("/data/bot.db"), ROOT / "data" / "bot.db")

    nsfw = Path("/data/metadata/nsfw_labels.json")
    if nsfw.is_file():
        _link(nsfw, ROOT / "data" / "metadata" / "nsfw_labels.json")


def main() -> None:
    setup_data_mount()
    raise SystemExit(subprocess.call([sys.executable, "-m", "bot.main"], cwd=ROOT))


if __name__ == "__main__":
    main()
