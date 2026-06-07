"""Определение: заглушка датасета или полный индекс на диске."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MIN_REAL_FACES = 100
DATA_SUBDIRS = ("index", "raw", "processed", "metadata")


def _load_mapping(mapping_path: Path) -> dict | None:
    if not mapping_path.is_file():
        return None
    try:
        return json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def embedding_face_count(index_dir: Path) -> int | None:
    embeddings_path = index_dir / "embeddings.npy"
    if not embeddings_path.is_file():
        return None
    try:
        embeddings = np.load(embeddings_path, mmap_mode="r")
        if embeddings.ndim != 2 or embeddings.shape[1] < 1:
            return None
        return int(embeddings.shape[0])
    except (OSError, ValueError):
        return None


def dataset_score(data_root: Path) -> int:
    index_dir = data_root / "index"
    face_count = embedding_face_count(index_dir) or 0
    mapping = _load_mapping(index_dir / "mapping.json")
    if mapping:
        face_count = max(
            face_count,
            int(mapping.get("total_faces", 0)),
            int(mapping.get("total_actresses", 0)),
            len(mapping.get("entries", [])),
        )
    return face_count


def resolve_data_root(project_root: Path) -> Path:
    """Каталог с датасетом: data/ или data/data/ при вложенной загрузке в Amvera."""
    canonical = project_root / "data"
    nested = canonical / "data"
    candidates = [canonical]
    if nested.is_dir():
        candidates.append(nested)

    best = canonical
    best_score = -1
    for root in candidates:
        score = dataset_score(root)
        if score > best_score:
            best_score = score
            best = root

    if best != canonical and best_score > dataset_score(canonical):
        logger.warning(
            "Датасет найден во вложенной папке %s (загрузили папку data/ в корень Data). "
            "Используем её вместо %s",
            nested,
            canonical,
        )
    return best


def resolve_data_path(data_root: Path, relative: str) -> Path:
    """Путь из mapping.json (data/processed/...) → реальный путь на диске."""
    path = Path(relative)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "data":
        return data_root / Path(*path.parts[1:])
    return data_root / path


def is_real_dataset(data_root: Path) -> bool:
    """True, если в persistence лежит полный датасет, а не bootstrap-заглушка."""
    index_dir = data_root / "index"
    mapping = _load_mapping(index_dir / "mapping.json")

    face_count = embedding_face_count(index_dir)
    if face_count is not None and face_count >= MIN_REAL_FACES:
        return True

    if mapping:
        if int(mapping.get("total_faces", 0)) >= MIN_REAL_FACES:
            return True
        if int(mapping.get("total_actresses", 0)) >= MIN_REAL_FACES:
            return True
        if len(mapping.get("entries", [])) >= MIN_REAL_FACES:
            return True
        if not mapping.get("stub", False) and int(mapping.get("total_actresses", 0)) >= 2:
            return True

    return False


def describe_dataset(data_root: Path, *, project_root: Path | None = None) -> str:
    index_dir = data_root / "index"
    mapping = _load_mapping(index_dir / "mapping.json")
    face_count = embedding_face_count(index_dir)
    processed_count = sum(
        1 for p in (data_root / "processed").iterdir() if p.is_dir()
    ) if (data_root / "processed").is_dir() else 0

    parts = [
        f"data_root={data_root}",
        f"index={index_dir}",
        f"embeddings_faces={face_count if face_count is not None else 'нет'}",
        f"mapping_stub={mapping.get('stub') if mapping else 'нет файла'}",
        f"mapping_total_faces={mapping.get('total_faces') if mapping else '—'}",
        f"processed_dirs={processed_count}",
        f"real={is_real_dataset(data_root)}",
    ]
    if project_root is not None:
        nested = project_root / "data" / "data"
        if nested.is_dir():
            parts.append(f"nested_score={dataset_score(nested)}")
    return ", ".join(parts)
