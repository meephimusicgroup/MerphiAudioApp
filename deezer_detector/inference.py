"""
MAI AI Detector — spectral (Fourier) artifact analysis.

Engine inspired by Deezer's ISMIR 2025 paper "A Fourier Explanation of
AI-music Artifacts" (Afchar et al.). Neural audio generators that rely on
transposed-convolution / upsampling stages leave *periodic* "checkerboard"
artifacts in the magnitude spectrum. Those artifacts show up as sharp,
regularly spaced peaks once you take the Fourier transform of the
time-averaged log-spectrum.

This is a fully analytical detector: it requires no trained weights and no
network download. It only depends on numpy + scipy + librosa.

The probability returned is a heuristic, calibrated so that natural
recordings tend to score low and audio with strong periodic spectral
regularity (typical of AI generation) scores high.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

try:
    from scipy.ndimage import uniform_filter1d
except Exception:  # pragma: no cover - scipy should always be present
    uniform_filter1d = None


class ModelNotReadyError(FileNotFoundError):
    """Kept for backward compatibility. The analytical engine is always ready."""


# Analysis parameters ------------------------------------------------------
_SAMPLE_RATE = 44100
_N_FFT = 4096
_HOP = 1024
_MAX_SECONDS = 60.0          # analyse at most the central 60 s for speed
_SLICE_SECONDS = 8.0         # length of each averaged slice
_NUM_SLICES = 5              # robustness: average artifact score over slices
_ENVELOPE_WINDOW = 61        # smoothing window (bins) for spectral detrending
_MIN_QUEFRENCY = 4           # ignore slow trend at the low quefrency end

# Logistic calibration (peak-to-background ratio -> probability)
#
# NOTE on calibration: DAW time-stretching / pitch-shifting (e.g. "slowed"
# edits) introduce strong, regular spectral/phase artifacts that resemble the
# periodic "checkerboard" patterns of AI deconvolution. A midpoint of 9 pushed
# those manipulated-but-human tracks (ratio ~19) to ~99% AI; a midpoint of 24
# went too far the other way and missed real AI tracks. 18.0 with a wide curve
# is the sweet spot between catching AI and ignoring standard DAW stretching.
# (Explicit AI metadata tags are handled separately in the hybrid path.)
_RATIO_MIDPOINT = 18.0
_RATIO_WIDTH = 5.5


def _smooth(values: np.ndarray, window: int) -> np.ndarray:
    if uniform_filter1d is not None:
        return uniform_filter1d(values, size=window, mode="nearest")
    kernel = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(values, kernel, mode="same")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


class MAIDetector:
    """Thread-safe singleton spectral AI-artifact detector."""

    _instance: "MAIDetector | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._ready = True

    @classmethod
    def get(cls) -> "MAIDetector":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def is_ready(self) -> bool:
        return True

    def ensure_ready(self) -> None:
        """No-op: the analytical engine needs no downloaded weights."""
        return None

    # -- core analysis -----------------------------------------------------

    def _load_mono(self, filepath: str | Path) -> np.ndarray:
        import librosa

        waveform, _ = librosa.load(
            str(filepath),
            sr=_SAMPLE_RATE,
            mono=True,
            dtype=np.float32,
        )
        if waveform.size == 0:
            raise ValueError("Audio file is empty or could not be decoded.")

        max_len = int(_MAX_SECONDS * _SAMPLE_RATE)
        if waveform.shape[0] > max_len:
            start = (waveform.shape[0] - max_len) // 2
            waveform = waveform[start : start + max_len]
        return waveform

    def _artifact_ratio(self, mono_slice: np.ndarray) -> float:
        """Peak-to-background ratio of periodic spectral artifacts in one slice."""
        import librosa

        if mono_slice.shape[0] < _N_FFT:
            mono_slice = np.pad(mono_slice, (0, _N_FFT - mono_slice.shape[0]))

        stft = librosa.stft(mono_slice, n_fft=_N_FFT, hop_length=_HOP, center=True)
        power = np.abs(stft) ** 2
        log_power = np.log10(np.clip(power, 1e-10, None))

        # Time-averaged spectrum across frequency bins.
        mean_spectrum = log_power.mean(axis=1)

        # Detrend: remove the natural smooth spectral envelope so only
        # periodic (artifact) structure remains.
        envelope = _smooth(mean_spectrum, _ENVELOPE_WINDOW)
        residual = mean_spectrum - envelope

        # Window the residual, then take its Fourier transform over frequency.
        window = np.hanning(residual.shape[0])
        spectrum_fft = np.abs(np.fft.rfft(residual * window))

        if spectrum_fft.shape[0] <= _MIN_QUEFRENCY + 2:
            return 0.0

        band = spectrum_fft[_MIN_QUEFRENCY:]
        background = np.median(band) + 1e-9
        peak = float(np.max(band))
        return peak / background

    def predict_file(self, filepath: str | Path) -> float:
        """
        Return AI-generation probability in [0, 1].

        0.0 ~ natural / human recording, 1.0 ~ strong AI spectral artifacts.
        """
        mono = self._load_mono(filepath)

        slice_len = int(_SLICE_SECONDS * _SAMPLE_RATE)
        if mono.shape[0] <= slice_len:
            ratios = [self._artifact_ratio(mono)]
        else:
            max_offset = mono.shape[0] - slice_len
            offsets = np.linspace(0, max_offset, num=_NUM_SLICES, dtype=int)
            ratios = [
                self._artifact_ratio(mono[off : off + slice_len])
                for off in offsets
            ]

        # Use a robust central tendency to resist single-slice outliers.
        ratio = float(np.median(ratios))
        probability = _sigmoid((ratio - _RATIO_MIDPOINT) / _RATIO_WIDTH)
        return float(np.clip(probability, 0.0, 1.0))


# Backward-compatible alias so existing imports keep working.
DeezerDeepfakeDetector = MAIDetector
