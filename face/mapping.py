from __future__ import annotations

import json
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
EMBEDDING_DIM = 512


def load_actress_names(metadata_dir: Path) -> dict[str, dict]:
    names: dict[str, dict] = {}
    if not metadata_dir.exists():
        return names

    for meta_file in metadata_dir.glob("*.json"):
        if meta_file.name == "dataset_summary.json":
            continue
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        slug = data.get("slug") or meta_file.stem
        names[slug] = {
            "name": data.get("name", slug),
            "thumbnail": data.get("thumbnail_url"),
            "profile_url": data.get("profile_url"),
        }
    return names


def build_mapping(
    processed_dir: Path,
    metadata_dir: Path,
    project_root: Path,
) -> dict:
    actress_meta = load_actress_names(metadata_dir)
    entries: list[dict] = []
    actress_indices: dict[str, list[int]] = {}

    for actress_dir in sorted(processed_dir.iterdir()):
        if not actress_dir.is_dir():
            continue
        slug = actress_dir.name
        for face_path in sorted(actress_dir.iterdir()):
            if face_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            idx = len(entries)
            entries.append(
                {
                    "index": idx,
                    "slug": slug,
                    "face_path": str(face_path.relative_to(project_root)),
                    "has_embedding": False,
                }
            )
            actress_indices.setdefault(slug, []).append(idx)

    actresses = {}
    for slug, indices in actress_indices.items():
        meta = actress_meta.get(slug, {})
        actresses[slug] = {
            "name": meta.get("name", slug.replace("_", " ").title()),
            "thumbnail": meta.get("thumbnail"),
            "profile_url": meta.get("profile_url"),
            "indices": indices,
            "face_count": len(indices),
        }

    return {
        "total_faces": len(entries),
        "total_actresses": len(actresses),
        "embedding_dim": EMBEDDING_DIM,
        "embeddings_ready": False,
        "faiss_ready": False,
        "entries": entries,
        "actresses": actresses,
    }
