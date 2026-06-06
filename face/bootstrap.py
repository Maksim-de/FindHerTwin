"""macOS: PyTorch + FAISS конфликтуют по libomp — разрешаем до импорта ML-библиотек."""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
