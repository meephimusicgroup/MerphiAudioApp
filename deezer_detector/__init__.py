"""MAI AI Detector — local spectral (Fourier) artifact analysis engine."""

from deezer_detector.inference import (
    DeezerDeepfakeDetector,
    MAIDetector,
    ModelNotReadyError,
)

__all__ = ["MAIDetector", "DeezerDeepfakeDetector", "ModelNotReadyError"]
