"""
Local inference for the Deezer deepfake-detector research model.

Runtime inference uses PyTorch. Pretrained weights are shipped as
models/specnn_amplitude.pt, generated once from the official TensorFlow
SavedModel via convert_tf_to_torch.py.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np
import torch

from deezer_detector.config import ConfLoader
from deezer_detector.model_torch import DeezerSpecCNN
from deezer_detector.preprocess import build_eval_slices


class ModelNotReadyError(FileNotFoundError):
    """Raised when pretrained Deezer weights are missing locally."""


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def models_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "models"  # type: ignore[attr-defined]
        if bundled.is_dir():
            return bundled
    return app_root() / "models"


def conf_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "deezer_detector" / "conf"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "conf"


class DeezerDeepfakeDetector:
    """Thread-safe lazy loader + PyTorch predictor for specnn_amplitude."""

    _instance: "DeezerDeepfakeDetector | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._model: DeezerSpecCNN | None = None
        self._conf: dict | None = None
        self._device = torch.device("cpu")
        self._load_lock = threading.Lock()

    @classmethod
    def get(cls) -> "DeezerDeepfakeDetector":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def weights_path(self) -> Path:
        return models_dir() / "specnn_amplitude.pt"

    def ensure_ready(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            if not self.weights_path.is_file():
                raise ModelNotReadyError(
                    "PyTorch weights not found.\n"
                    "Run:\n"
                    "  python download_model.py\n"
                    "  python convert_tf_to_torch.py"
                )

            loader = ConfLoader(conf_dir())
            loader.load_model("specnn_amplitude")
            self._conf = loader.conf

            model = DeezerSpecCNN()
            state_dict = torch.load(
                self.weights_path,
                map_location=self._device,
                weights_only=True,
            )
            model.load_state_dict(state_dict)
            model.to(self._device)
            model.eval()
            self._model = model

    def predict_file(self, filepath: str | Path) -> float:
        """
        Return AI/deepfake probability in [0, 1].

        0.0 ~ human / authentic, 1.0 ~ AI / deepfake (Deezer sigmoid head).
        """
        self.ensure_ready()
        assert self._model is not None
        assert self._conf is not None

        specs = build_eval_slices(filepath, self._conf)
        probabilities: list[float] = []

        for spec in specs:
            tensor = torch.from_numpy(np.transpose(spec, (2, 0, 1))).unsqueeze(0)
            tensor = tensor.to(self._device, dtype=torch.float32)
            probabilities.append(self._model.predict_deepfake_probability(tensor))

        return float(np.mean(probabilities))
