from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch
from facenet_pytorch import MTCNN
from PIL import Image, ImageFile, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Частично скачанные JPEG/WebP иногда читаются целиком
ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def get_detector_device() -> torch.device:
    # MTCNN на MPS падает на части изображений (PyTorch #96056)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class FaceDetector:
    """MTCNN — детекция и кроп лиц до 160×160."""

    def __init__(
        self,
        image_size: int = 160,
        margin: int = 20,
        min_face_size: int = 40,
        min_probability: float = 0.90,
        device: torch.device | None = None,
    ) -> None:
        self.image_size = image_size
        self.margin = margin
        self.min_probability = min_probability
        self.device = device or get_detector_device()
        self.last_load_ok = True
        self.mtcnn = MTCNN(
            image_size=image_size,
            margin=margin,
            min_face_size=min_face_size,
            device=self.device,
            keep_all=False,
        )

    def detect_and_crop(self, image: Image.Image) -> torch.Tensor | None:
        boxes, probs = self.mtcnn.detect(image)
        if boxes is None or probs is None:
            return None

        candidates: list[tuple[np.ndarray, float]] = []
        for box, prob in zip(boxes, probs):
            if prob is None or prob < self.min_probability:
                continue
            candidates.append((box, float(prob)))

        if not candidates:
            return None

        box, _ = max(
            candidates,
            key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1]),
        )
        return self._crop_box(image, box)

    def _crop_box(self, image: Image.Image, box: np.ndarray) -> torch.Tensor | None:
        x1, y1, x2, y2 = box.astype(int)
        w, h = image.size
        m = self.margin
        x1 = max(0, x1 - m)
        y1 = max(0, y1 - m)
        x2 = min(w, x2 + m)
        y2 = min(h, y2 + m)
        if x2 <= x1 or y2 <= y1:
            return None

        face = image.crop((x1, y1, x2, y2)).resize(
            (self.image_size, self.image_size),
            Image.Resampling.LANCZOS,
        )
        array = np.array(face)
        return torch.from_numpy(array.copy()).permute(2, 0, 1).byte()

    def crop_from_path(self, image_path: Path) -> torch.Tensor | None:
        self.last_load_ok = True
        try:
            with Image.open(image_path) as img:
                img.load()
                return self.detect_and_crop(img.convert("RGB"))
        except (OSError, UnidentifiedImageError) as exc:
            self.last_load_ok = False
            logger.warning("Повреждённый файл, пропуск: %s (%s)", image_path, exc)
            return None

    @staticmethod
    def save_crop(face_tensor: torch.Tensor, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        array = face_tensor.permute(1, 2, 0).byte().cpu().numpy()
        Image.fromarray(array).save(output_path, quality=95)
