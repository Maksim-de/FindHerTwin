from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np


@dataclass
class SearchResult:
    slug: str
    name: str
    score: float
    face_path: str
    thumbnail: str | None = None


class FaceIndex:
    """FAISS-индекс с агрегацией по актрисе (лучший score среди её лиц)."""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.index_path = index_dir / "faiss.index"
        self.mapping_path = index_dir / "mapping.json"
        self.embeddings_path = index_dir / "embeddings.npy"

        self.index: faiss.IndexFlatIP | None = None
        self.embeddings: np.ndarray | None = None
        self.mapping: dict = {}

    def build(self, embeddings: np.ndarray, mapping: dict) -> None:
        vectors = embeddings.astype(np.float32).copy()
        faiss.normalize_L2(vectors)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        np.save(self.embeddings_path, vectors)
        self.mapping_path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.index = index
        self.embeddings = vectors
        self.mapping = mapping

    def load(self) -> None:
        if not self.index_path.exists() or not self.mapping_path.exists():
            raise FileNotFoundError(
                f"Индекс не найден в {self.index_dir}. Сначала запустите build_index.py"
            )
        self.index = faiss.read_index(str(self.index_path))
        self.mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        if self.embeddings_path.exists():
            self.embeddings = np.load(self.embeddings_path)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        search_pool: int = 50,
    ) -> list[SearchResult]:
        if self.index is None:
            self.load()

        assert self.index is not None
        query = query_embedding.astype(np.float32).reshape(1, -1).copy()
        faiss.normalize_L2(query)

        pool = min(search_pool, self.index.ntotal)
        scores, indices = self.index.search(query, pool)

        entries = self.mapping["entries"]
        actresses_meta = self.mapping["actresses"]

        best_per_slug: dict[str, SearchResult] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            entry = entries[idx]
            slug = entry["slug"]
            if slug not in best_per_slug or score > best_per_slug[slug].score:
                meta = actresses_meta.get(slug, {})
                best_per_slug[slug] = SearchResult(
                    slug=slug,
                    name=meta.get("name", slug),
                    score=float(score),
                    face_path=entry["face_path"],
                    thumbnail=meta.get("thumbnail"),
                )

        results = sorted(best_per_slug.values(), key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def rank_actress_faces(
        self, slug: str, query_embedding: np.ndarray
    ) -> list[tuple[float, str]]:
        """Лица актрисы, отсортированные по похожести на query (убывание)."""
        if self.embeddings is None:
            if self.embeddings_path.exists():
                self.embeddings = np.load(self.embeddings_path)
            else:
                return []

        query = query_embedding.astype(np.float32).reshape(1, -1).copy()
        faiss.normalize_L2(query)
        q = query[0]

        ranked: list[tuple[float, str]] = []
        for entry in self.mapping["entries"]:
            if entry["slug"] != slug:
                continue
            idx = entry["index"]
            emb = self.embeddings[idx].astype(np.float32).copy()
            faiss.normalize_L2(emb.reshape(1, -1))
            score = float(np.dot(q, emb))
            ranked.append((score, entry["face_path"]))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked

    def get_embedding_for_actress(
        self, slug: str, face_num: str | None = None
    ) -> np.ndarray | None:
        if self.embeddings is None:
            if self.embeddings_path.exists():
                self.embeddings = np.load(self.embeddings_path)
            else:
                return None

        target_path = None
        if face_num is not None:
            target_path = f"data/processed/{slug}/face_{face_num}.jpg"

        for entry in self.mapping["entries"]:
            if entry["slug"] != slug:
                continue
            if target_path and entry["face_path"] != target_path:
                continue
            idx = entry["index"]
            return self.embeddings[idx].copy()

        return None
