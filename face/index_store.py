from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class SearchResult:
    slug: str
    name: str
    score: float
    face_path: str
    thumbnail: str | None = None


def _normalize_l2_rows(vectors: np.ndarray) -> np.ndarray:
    out = vectors.astype(np.float32).copy()
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    out /= norms
    return out


def _normalize_l2_vector(vector: np.ndarray) -> np.ndarray:
    out = vector.astype(np.float32).reshape(-1).copy()
    norm = float(np.linalg.norm(out))
    if norm > 1e-12:
        out /= norm
    return out


class FaceIndex:
    """Индекс лиц с агрегацией по актрисе (лучший score среди её лиц).

    Поиск в рантайме — через numpy (без FAISS), чтобы на macOS не конфликтовать
    с PyTorch. FAISS используется только при сборке индекса (build_index.py).
    """

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.index_path = index_dir / "faiss.index"
        self.mapping_path = index_dir / "mapping.json"
        self.embeddings_path = index_dir / "embeddings.npy"

        self.embeddings: np.ndarray | None = None
        self.mapping: dict = {}

    def build(self, embeddings: np.ndarray, mapping: dict) -> None:
        import faiss

        vectors = _normalize_l2_rows(embeddings)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        np.save(self.embeddings_path, vectors)
        self.mapping_path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.embeddings = vectors
        self.mapping = mapping

    def load(self) -> None:
        if not self.mapping_path.exists():
            raise FileNotFoundError(
                f"Индекс не найден в {self.index_dir}. Сначала запустите build_index.py"
            )
        if not self.embeddings_path.exists():
            raise FileNotFoundError(
                f"embeddings.npy не найден в {self.index_dir}. "
                "Сначала: python scripts/generate_embeddings.py"
            )

        self.mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        self.embeddings = np.load(self.embeddings_path)

    @property
    def total_faces(self) -> int:
        return int(self.embeddings.shape[0]) if self.embeddings is not None else 0

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        search_pool: int = 50,
    ) -> list[SearchResult]:
        if self.embeddings is None:
            self.load()

        assert self.embeddings is not None
        query = _normalize_l2_vector(query_embedding)
        scores = self.embeddings @ query

        pool = min(search_pool, scores.shape[0])
        if pool <= 0:
            return []

        candidate_idx = np.argpartition(-scores, pool - 1)[:pool]
        candidate_idx = candidate_idx[np.argsort(-scores[candidate_idx])]

        entries = self.mapping["entries"]
        actresses_meta = self.mapping["actresses"]

        best_per_slug: dict[str, SearchResult] = {}
        for idx in candidate_idx:
            score = float(scores[idx])
            entry = entries[int(idx)]
            slug = entry["slug"]
            if slug not in best_per_slug or score > best_per_slug[slug].score:
                meta = actresses_meta.get(slug, {})
                best_per_slug[slug] = SearchResult(
                    slug=slug,
                    name=meta.get("name", slug),
                    score=score,
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
            self.load()

        assert self.embeddings is not None
        query = _normalize_l2_vector(query_embedding)

        ranked: list[tuple[float, str]] = []
        for entry in self.mapping["entries"]:
            if entry["slug"] != slug:
                continue
            idx = entry["index"]
            emb = self.embeddings[idx]
            score = float(np.dot(query, emb))
            ranked.append((score, entry["face_path"]))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked

    def get_embedding_for_actress(
        self, slug: str, face_num: str | None = None
    ) -> np.ndarray | None:
        if self.embeddings is None:
            self.load()

        assert self.embeddings is not None

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
