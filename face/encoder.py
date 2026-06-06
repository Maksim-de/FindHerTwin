from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1, fixed_image_standardization
from PIL import Image
from torchvision import transforms

from face.detector import FaceDetector, get_device


class FaceEncoder:
    """InceptionResnetV1 (VGGFace2) — 512-d embeddings."""

    def __init__(self, device: torch.device | None = None) -> None:
        self.device = device or get_device()
        self.model = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
        self.resize = transforms.Resize((160, 160))

    def _tensor_from_crop(self, face_tensor: torch.Tensor) -> torch.Tensor:
        batch = face_tensor.unsqueeze(0).to(self.device)
        batch = fixed_image_standardization(batch.float())
        with torch.no_grad():
            return self.model(batch).cpu().numpy()[0]

    def encode_crop_tensor(self, face_tensor: torch.Tensor) -> np.ndarray:
        return self._tensor_from_crop(face_tensor)

    def encode_crop_path(self, crop_path: Path) -> np.ndarray | None:
        with Image.open(crop_path) as img:
            tensor = transforms.ToTensor()(self.resize(img.convert("RGB")))
            tensor = (tensor * 255).clamp(0, 255)
            return self._tensor_from_crop(tensor)

    def encode_photo_path(
        self,
        photo_path: Path,
        detector: FaceDetector,
    ) -> np.ndarray | None:
        crop = detector.crop_from_path(photo_path)
        if crop is None:
            return None
        return self.encode_crop_tensor(crop)
