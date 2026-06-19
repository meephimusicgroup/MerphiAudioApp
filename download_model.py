#!/usr/bin/env python3
"""
Download Deezer deepfake-detector pretrained weights into ./models/

Run once before first AI analysis:
    python download_model.py
    python convert_tf_to_torch.py
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_RAW = "https://raw.githubusercontent.com/deezer/deepfake-detector/main"
WEIGHT_FILES = [
    "weights/final/specnn_amplitude/saved_model.pb",
    "weights/final/specnn_amplitude/keras_metadata.pb",
    "weights/final/specnn_amplitude/fingerprint.pb",
    "weights/final/specnn_amplitude/variables/variables.index",
    "weights/final/specnn_amplitude/variables/variables.data-00000-of-00001",
]

APP_ROOT = Path(__file__).resolve().parent
TF_MODEL_DIR = APP_ROOT / "models" / "specnn_amplitude"
TORCH_WEIGHTS_PATH = APP_ROOT / "models" / "specnn_amplitude.pt"


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "MerphiAudioInspector/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    destination.write_bytes(data)
    print(f"  -> {destination} ({len(data) / (1024 * 1024):.2f} MB)")


def _download_tensorflow_weights() -> None:
    if TF_MODEL_DIR.is_dir() and (TF_MODEL_DIR / "saved_model.pb").is_file():
        print("TensorFlow SavedModel already present.")
        return

    for repo_path in WEIGHT_FILES:
        url = f"{REPO_RAW}/{repo_path}"
        relative = repo_path.split("weights/final/specnn_amplitude/", 1)[1]
        destination = TF_MODEL_DIR / relative
        _download(url, destination)


def _try_convert_to_pytorch() -> bool:
    if TORCH_WEIGHTS_PATH.is_file():
        print("PyTorch weights already present.")
        return True

    # Conversion is pure Python + NumPy (no TensorFlow needed).
    print("\nConverting TensorFlow weights to PyTorch...")
    result = subprocess.run(
        [sys.executable, str(APP_ROOT / "convert_tf_to_torch.py")],
        cwd=APP_ROOT,
        check=False,
    )
    return result.returncode == 0 and TORCH_WEIGHTS_PATH.is_file()


def main() -> int:
    print("Merphi Audio Inspector - Deezer model downloader")
    print(f"TensorFlow target: {TF_MODEL_DIR}")
    print(f"PyTorch target:  {TORCH_WEIGHTS_PATH}\n")

    try:
        _download_tensorflow_weights()
    except urllib.error.URLError as exc:
        print(f"\nDownload failed: {exc}")
        print("Check your internet connection and try again.")
        return 1

    _try_convert_to_pytorch()

    if TORCH_WEIGHTS_PATH.is_file():
        print("\nDone. You can now run: python main.py")
        return 0

    print(
        "\nDownload complete, but PyTorch weights are still missing.\n"
        "Run: python convert_tf_to_torch.py"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
