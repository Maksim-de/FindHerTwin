"""Face recognition pipeline (lazy imports — torch и faiss не грузятся вместе)."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["FaceDetector", "FaceEncoder", "FaceIndex"]


def __getattr__(name: str):
    if name == "FaceDetector":
        from face.detector import FaceDetector

        return FaceDetector
    if name == "FaceEncoder":
        from face.encoder import FaceEncoder

        return FaceEncoder
    if name == "FaceIndex":
        from face.index_store import FaceIndex

        return FaceIndex
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
