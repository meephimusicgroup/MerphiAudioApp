"""
Audio preprocessing pipeline for the Deezer specnn_amplitude model.

Mirrors EvalAugmenter in deezer/deepfake-detector/loader/audio.py:
mono mix -> STFT dB -> normalise -> high-frequency crop.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def load_stereo_audio(filepath: str | Path, target_sr: int) -> np.ndarray:
    """Return stereo waveform shaped (samples, 2)."""
    waveform, _ = librosa.load(
        str(filepath),
        sr=target_sr,
        mono=False,
        dtype=np.float32,
    )

    if waveform.ndim == 1:
        waveform = np.stack([waveform, waveform], axis=0)

    # librosa returns (channels, samples); convert to (samples, channels)
    if waveform.shape[0] == 2:
        waveform = waveform.T

    if waveform.shape[1] == 1:
        waveform = np.repeat(waveform, 2, axis=1)

    return waveform.astype(np.float32)


def _to_mono_eval(waveform: np.ndarray) -> np.ndarray:
    return (0.5 * waveform[:, 0] + 0.5 * waveform[:, 1]).astype(np.float32)


def _slice_center(mono: np.ndarray, target_len: int) -> np.ndarray:
    if mono.shape[0] < target_len:
        pad = target_len - mono.shape[0]
        mono = np.pad(mono, (0, pad), mode="constant")
    start = max(0, (mono.shape[0] - target_len) // 2)
    return mono[start : start + target_len]


def _stft_db(
    mono: np.ndarray,
    n_fft: int,
    hop_length: int,
    win_length: int,
) -> np.ndarray:
    complex_stft = librosa.stft(
        mono,
        n_fft=n_fft,
        hop_length=hop_length,
        win_length=win_length,
        center=True,
    )
    power = np.square(np.abs(complex_stft))
    spec_db = np.log10(np.clip(power, 1e-10, 1e6))
    return spec_db.T.astype(np.float32)


def _normalise(spec: np.ndarray, mean: float, std: float) -> np.ndarray:
    return ((spec - mean) / std).astype(np.float32)


def _slice_hf(spec: np.ndarray, hf_cut: int, sample_rate: int) -> np.ndarray:
    factor = int((hf_cut * 2 / sample_rate) * spec.shape[1])
    factor = max(1, min(factor, spec.shape[1]))
    return spec[:, :factor]


def _fit_model_input(spec: np.ndarray, target_t: int = 64, target_f: int = 64) -> np.ndarray:
    """Crop/pad spectrogram to the Deezer model's fixed 64x64 input."""
    time_bins, freq_bins = spec.shape[:2]

    if time_bins >= target_t:
        start = (time_bins - target_t) // 2
        spec = spec[start : start + target_t, :]
    else:
        spec = np.pad(spec, ((0, target_t - time_bins), (0, 0)))

    if freq_bins >= target_f:
        spec = spec[:, :target_f]
    else:
        spec = np.pad(spec, ((0, 0), (0, target_f - freq_bins)))

    return spec.astype(np.float32)


def waveform_to_spectrogram(waveform: np.ndarray, conf: dict) -> np.ndarray:
    sample_rate = int(conf["sr"])
    fft_conf = conf["fft"]
    mono = _to_mono_eval(waveform)
    spec = _stft_db(
        mono,
        n_fft=int(fft_conf["n_fft"]),
        hop_length=int(fft_conf["hop"]),
        win_length=int(fft_conf["win"]),
    )
    spec = _normalise(spec, float(conf["normalise_mean"]), float(conf["normalise_std"]))
    spec = _slice_hf(spec, int(conf["hf_cut"]), sample_rate)
    spec = _fit_model_input(spec)
    return spec[..., np.newaxis]


def build_eval_slices(filepath: str | Path, conf: dict) -> list[np.ndarray]:
    """
    Build multiple evaluation slices (repeat=5 in the Deezer config) to stabilise scores.
    """
    sample_rate = int(conf["sr"])
    slice_seconds = float(conf.get("audio_slice", 0.78))
    repeat = int(conf.get("repeat", 5))
    target_len = int(slice_seconds * sample_rate)

    waveform = load_stereo_audio(filepath, sample_rate)
    mono = _to_mono_eval(waveform)

    if mono.shape[0] <= target_len:
        chunk = _slice_center(mono, target_len)
        stereo_chunk = np.stack([chunk, chunk], axis=1)
        return [waveform_to_spectrogram(stereo_chunk, conf)]

    max_offset = mono.shape[0] - target_len
    offsets = np.linspace(0, max_offset, num=repeat, dtype=int)
    specs: list[np.ndarray] = []

    for offset in offsets:
        chunk = mono[offset : offset + target_len]
        stereo_chunk = np.stack([chunk, chunk], axis=1)
        specs.append(waveform_to_spectrogram(stereo_chunk, conf))

    return specs
