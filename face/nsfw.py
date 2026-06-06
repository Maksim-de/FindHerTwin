from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

NsfwLevel = Literal["safe", "explicit", "unknown"]

# NudeNet v3 — открытые интимные зоны = explicit
EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    # v2 совместимость
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_ANUS",
    "EXPOSED_BUTTOCKS",
    "EXPOSED_BREAST_F",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class NsfwClassifier:
    """Классификация: safe (одежда/белье/лицо) vs explicit (нюдс)."""

    def __init__(self, min_score: float = 0.4) -> None:
        from nudenet import NudeDetector

        self.min_score = min_score
        self.detector = NudeDetector()
        logger.info("NsfwClassifier готов")

    def classify_image(self, image_path: Path) -> NsfwLevel:
        try:
            detections = self.detector.detect(str(image_path))
        except Exception as exc:
            logger.warning("NSFW detect failed %s: %s", image_path, exc)
            return "unknown"

        for det in detections:
            if det.get("score", 0) < self.min_score:
                continue
            if det.get("class") in EXPLICIT_CLASSES:
                return "explicit"
        return "safe"

    def classify_batch(self, image_paths: list[Path]) -> dict[str, NsfwLevel]:
        if not image_paths:
            return {}
        try:
            batch_result = self.detector.detect_batch([str(p) for p in image_paths])
        except Exception:
            return {p.name: self.classify_image(p) for p in image_paths}

        out: dict[str, NsfwLevel] = {}
        for path, detections in zip(image_paths, batch_result):
            level: NsfwLevel = "safe"
            for det in detections:
                if det.get("score", 0) < self.min_score:
                    continue
                if det.get("class") in EXPLICIT_CLASSES:
                    level = "explicit"
                    break
            out[path.name] = level
        return out


class NsfwLabelStore:
    """Хранилище разметки: data/metadata/nsfw_labels.json"""

    def __init__(self, labels_path: Path) -> None:
        self.labels_path = labels_path
        self._data: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self.labels_path.exists():
            self._data = json.loads(self.labels_path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.labels_path.parent.mkdir(parents=True, exist_ok=True)
        self.labels_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_actress_labels(self, slug: str, labels: dict[str, NsfwLevel]) -> None:
        self._data[slug] = labels

    def get_label(self, slug: str, filename: str) -> NsfwLevel:
        return self._data.get(slug, {}).get(filename, "unknown")  # type: ignore[return-value]

    def is_sendable(self, slug: str, filename: str) -> bool:
        return self.get_label(slug, filename) == "safe"

    def find_sendable_photo(self, slug: str, raw_dir: Path, prefer: Path | None = None) -> Path | None:
        if not raw_dir.exists():
            return None

        candidates = sorted(
            p for p in raw_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not candidates:
            return None

        if prefer and prefer.exists() and self.is_sendable(slug, prefer.name):
            return prefer

        for path in candidates:
            if self.is_sendable(slug, path.name):
                return path

        return None
