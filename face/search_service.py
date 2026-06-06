from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import face.bootstrap  # noqa: F401

import numpy as np
import yaml
from PIL import Image

from face.detector import FaceDetector, get_device
from face.encoder import FaceEncoder
from face.index_store import FaceIndex, SearchResult
from face.nsfw import NsfwLabelStore

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class ActressMatch:
    rank: int
    name: str
    slug: str
    score: float
    face_crop: Path
    raw_photo: Path | None
    profile_url: str | None


class FaceSearchService:
    """Синглтон поиска: модели загружаются один раз при старте бота."""

    def __init__(self, config_path: Path | None = None) -> None:
        config_path = config_path or PROJECT_ROOT / "config.yaml"
        with config_path.open(encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}

        paths = self.config.get("paths", {})
        face_cfg = self.config.get("face", {})

        self.index_dir = PROJECT_ROOT / paths.get("index", "data/index")
        self.metadata_dir = PROJECT_ROOT / paths.get("metadata", "data/metadata")
        self.top_k = face_cfg.get("search_top_k", 5)
        self.min_prob = face_cfg.get("min_face_probability", 0.90)

        logger.info("Загрузка FAISS-индекса...")
        self.face_index = FaceIndex(self.index_dir)
        self.face_index.load()

        logger.info("Загрузка FaceNet (устройство: %s)...", get_device())
        self.detector = FaceDetector(min_probability=self.min_prob)
        self.encoder = FaceEncoder()
        self._metadata_cache: dict[str, dict] = {}
        nsfw_cfg = self.config.get("nsfw", {})
        self.nsfw_enabled = nsfw_cfg.get("enabled", True)
        labels_file = PROJECT_ROOT / nsfw_cfg.get(
            "labels_file", "data/metadata/nsfw_labels.json"
        )
        self.nsfw_labels_ready = labels_file.exists()
        self.nsfw_store = NsfwLabelStore(labels_file) if self.nsfw_enabled else None
        if self.nsfw_enabled and not self.nsfw_labels_ready:
            logger.warning(
                "NSFW-разметка не найдена (%s). Запустите: python scripts/label_nsfw.py",
                labels_file,
            )
        logger.info("FaceSearchService готов")

    def get_actress_name(self, slug: str) -> str:
        return self._load_metadata(slug).get("name", slug)

    def match_from_parts(
        self,
        rank: int,
        slug: str,
        face_num: str,
        name: str,
        score: float,
        profile_url: str | None = None,
    ) -> ActressMatch:
        face_crop = PROJECT_ROOT / "data" / "processed" / slug / f"face_{face_num}.jpg"
        raw_photo = self._guess_raw_path(face_crop)
        if profile_url is None:
            profile_url = self._load_metadata(slug).get("profile_url")
        return ActressMatch(
            rank=rank,
            name=name,
            slug=slug,
            score=score,
            face_crop=face_crop,
            raw_photo=raw_photo,
            profile_url=profile_url,
        )

    def _load_metadata(self, slug: str) -> dict:
        if slug in self._metadata_cache:
            return self._metadata_cache[slug]
        meta_file = self.metadata_dir / f"{slug}.json"
        if not meta_file.exists():
            return {}
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        self._metadata_cache[slug] = data
        return data

    @staticmethod
    def _resolve_face_path(face_path: str) -> Path:
        path = Path(face_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    def _guess_raw_path(self, face_path: Path) -> Path | None:
        slug = face_path.parent.name
        face_num = face_path.stem.removeprefix("face_")
        raw_dir = PROJECT_ROOT / "data" / "raw" / slug
        for ext in IMAGE_EXTENSIONS:
            candidate = raw_dir / f"{face_num}{ext}"
            if candidate.exists():
                return candidate
        return None

    def encode_image(self, image_path: Path) -> np.ndarray | None:
        with Image.open(image_path) as img:
            is_face_crop = img.size == (160, 160)
        if is_face_crop:
            return self.encoder.encode_crop_path(image_path)
        return self.encoder.encode_photo_path(image_path, self.detector)

    @staticmethod
    def _as_embedding(query_embedding: np.ndarray | list[float] | None) -> np.ndarray | None:
        if query_embedding is None:
            return None
        if isinstance(query_embedding, list):
            if not query_embedding:
                return None
            return np.asarray(query_embedding, dtype=np.float32)
        return query_embedding

    def _to_match(self, rank: int, result: SearchResult) -> ActressMatch:
        face_abs = self._resolve_face_path(result.face_path)
        raw_abs = self._guess_raw_path(face_abs)
        meta = self._load_metadata(result.slug)
        return ActressMatch(
            rank=rank,
            name=result.name,
            slug=result.slug,
            score=result.score,
            face_crop=face_abs,
            raw_photo=raw_abs,
            profile_url=meta.get("profile_url"),
        )

    def search_from_embedding(
        self, embedding: np.ndarray, top_k: int | None = None
    ) -> list[ActressMatch]:
        k = top_k or self.top_k
        results = self.face_index.search(embedding, top_k=k)
        return [self._to_match(i + 1, r) for i, r in enumerate(results)]

    def search(self, image_path: Path, top_k: int | None = None) -> list[ActressMatch]:
        embedding = self.encode_image(image_path)
        if embedding is None:
            return []
        return self.search_from_embedding(embedding, top_k=top_k)

    def get_actress_embedding(
        self, slug: str, face_num: str | None = None
    ) -> np.ndarray | None:
        return self.face_index.get_embedding_for_actress(slug, face_num)

    def search_similar_from_embedding(
        self,
        embedding: np.ndarray,
        exclude_slug: str,
        top_k: int | None = None,
    ) -> list[ActressMatch]:
        k = top_k or self.top_k
        pool = max(k * 10, 50)
        results = self.face_index.search(embedding, top_k=k + 1, search_pool=pool)
        filtered = [r for r in results if r.slug != exclude_slug][:k]
        return [self._to_match(i + 1, r) for i, r in enumerate(filtered)]

    def search_similar_to_actress(
        self,
        slug: str,
        face_num: str | None = None,
        top_k: int | None = None,
    ) -> list[ActressMatch]:
        """Похожие актрисы по эмбеддингу из базы (без самой актрисы в выдаче)."""
        embedding = self.get_actress_embedding(slug, face_num)
        if embedding is None:
            return []
        return self.search_similar_from_embedding(embedding, exclude_slug=slug, top_k=top_k)

    def best_photo_path(
        self,
        match: ActressMatch,
        query_embedding: np.ndarray | list[float] | None = None,
    ) -> Path | None:
        """Safe-фото: лучшее по query среди safe-кадров актрисы."""
        if (
            not self.nsfw_enabled
            or self.nsfw_store is None
            or not self.nsfw_labels_ready
        ):
            if match.raw_photo and match.raw_photo.exists():
                return match.raw_photo
            return match.face_crop if match.face_crop.exists() else None

        embedding = self._as_embedding(query_embedding)
        if embedding is not None:
            ranked_faces = self.face_index.rank_actress_faces(match.slug, embedding)
            for _score, face_path in ranked_faces:
                face_abs = self._resolve_face_path(face_path)
                raw = self._guess_raw_path(face_abs)
                if raw and self.nsfw_store.is_sendable(match.slug, raw.name):
                    return raw
            return None

        raw_dir = PROJECT_ROOT / "data" / "raw" / match.slug
        return self.nsfw_store.find_sendable_photo(
            match.slug, raw_dir, prefer=match.raw_photo
        )
