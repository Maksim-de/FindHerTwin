#!/usr/bin/env python3
"""Склейка нейро-кота и screen recording для Reels."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
VIDEO = ROOT / "video"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

INTRO = VIDEO / "Hailuo_Video_Vertical 9_16, dramatic courtr_519940772971184135.mp4"
SCREEN = VIDEO / "ScreenRecording_06-07-2026 10-46-46_1.MP4"
OUT = VIDEO / "reels_cat_judge_v1.mp4"

# Вертикаль 1080x1920 под Instagram Reels
VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    if not INTRO.is_file() or not SCREEN.is_file():
        print("Нужны файлы в video/", file=sys.stderr)
        return 1

    intro_norm = VIDEO / "_intro_norm.mp4"
    screen_norm = VIDEO / "_screen_norm.mp4"
    concat_list = VIDEO / "_concat.txt"

    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(INTRO),
            "-vf",
            VF,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            str(intro_norm),
        ]
    )

    # 8–20 c: загрузка фото → top-5 (81%)
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            "8",
            "-to",
            "20",
            "-i",
            str(SCREEN),
            "-vf",
            f"{VF},setpts=0.9*PTS",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            str(screen_norm),
        ]
    )

    concat_list.write_text(
        f"file '{intro_norm.name}'\nfile '{screen_norm.name}'\n",
        encoding="utf-8",
    )

    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(OUT),
        ]
    )

    for tmp in (intro_norm, screen_norm, concat_list):
        tmp.unlink(missing_ok=True)

    print(f"Готово: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
