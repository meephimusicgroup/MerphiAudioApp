#!/usr/bin/env python3
"""
Convert Deezer TensorFlow checkpoint weights to PyTorch (.pt).

This reads the TensorFlow checkpoint directly (pure Python + NumPy), so it
does NOT require TensorFlow and works on any Python version, including 3.14.

Usage:
    python convert_tf_to_torch.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import torch

from deezer_detector.model_torch import DeezerSpecCNN
from deezer_detector.tf_checkpoint import read_checkpoint

APP_ROOT = Path(__file__).resolve().parent
TF_MODEL_DIR = APP_ROOT / "models" / "specnn_amplitude"
VARIABLES_DIR = TF_MODEL_DIR / "variables"
TORCH_WEIGHTS_PATH = APP_ROOT / "models" / "specnn_amplitude.pt"

# BundleEntryProto attribute suffix used by Keras SavedModel checkpoints.
_SUFFIX = "/.ATTRIBUTES/VARIABLE_VALUE"
_LAYER_RE = re.compile(r"layer_with_weights-(\d+)/([a-z_]+)" + re.escape(_SUFFIX))


def _group_by_layer(tensors: dict[str, np.ndarray]) -> dict[int, dict[str, np.ndarray]]:
    layers: dict[int, dict[str, np.ndarray]] = {}
    for name, array in tensors.items():
        match = _LAYER_RE.match(name)
        if not match:
            continue
        layer_idx = int(match.group(1))
        attr = match.group(2)
        layers.setdefault(layer_idx, {})[attr] = array
    return layers


def _assign_weights(torch_model: DeezerSpecCNN, layers: dict[int, dict]) -> None:
    # Layer ordering in the Deezer SavedModel:
    #   even indices 0,2,4,6,8,10  -> conv2d blocks
    #   odd  indices 1,3,5,7,9,11  -> batch normalization blocks
    #   12 -> dense, 13 -> deepfake head, 14 -> encoder head (ignored)
    conv_layers = [layers[i] for i in (0, 2, 4, 6, 8, 10)]
    bn_layers = [layers[i] for i in (1, 3, 5, 7, 9, 11)]

    conv_modules = [m for m in torch_model.features if isinstance(m, torch.nn.Conv2d)]
    bn_modules = [m for m in torch_model.features if isinstance(m, torch.nn.BatchNorm2d)]

    for module, weights in zip(conv_modules, conv_layers):
        kernel = weights["kernel"]  # TF: (kh, kw, in, out)
        bias = weights["bias"]
        module.weight.data.copy_(
            torch.from_numpy(np.transpose(kernel, (3, 2, 0, 1)).copy()).float()
        )
        module.bias.data.copy_(torch.from_numpy(bias.copy()).float())

    for module, weights in zip(bn_modules, bn_layers):
        module.weight.data.copy_(torch.from_numpy(weights["gamma"].copy()).float())
        module.bias.data.copy_(torch.from_numpy(weights["beta"].copy()).float())
        module.running_mean.data.copy_(
            torch.from_numpy(weights["moving_mean"].copy()).float()
        )
        module.running_var.data.copy_(
            torch.from_numpy(weights["moving_variance"].copy()).float()
        )

    dense = layers[12]
    torch_model.head[1].weight.data.copy_(
        torch.from_numpy(dense["kernel"].T.copy()).float()
    )
    torch_model.head[1].bias.data.copy_(torch.from_numpy(dense["bias"].copy()).float())

    deepfake = layers[13]
    torch_model.head[3].weight.data.copy_(
        torch.from_numpy(deepfake["kernel"].T.copy()).float()
    )
    torch_model.head[3].bias.data.copy_(
        torch.from_numpy(deepfake["bias"].copy()).float()
    )


def convert() -> Path:
    if not VARIABLES_DIR.is_dir():
        raise SystemExit(
            f"TensorFlow checkpoint not found: {VARIABLES_DIR}\n"
            "Run: python download_model.py"
        )

    print("Reading TensorFlow checkpoint (no TensorFlow required)...")
    tensors = read_checkpoint(VARIABLES_DIR)
    layers = _group_by_layer(tensors)

    required = set(range(14))  # layers 0..13 (encoder head 14 optional)
    missing = required - set(layers)
    if missing:
        raise SystemExit(
            f"Checkpoint is missing expected layers: {sorted(missing)}.\n"
            "The downloaded weights may be incomplete; re-run download_model.py."
        )

    torch_model = DeezerSpecCNN()
    _assign_weights(torch_model, layers)
    torch_model.eval()

    TORCH_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(torch_model.state_dict(), TORCH_WEIGHTS_PATH)
    return TORCH_WEIGHTS_PATH


def main() -> int:
    output = convert()
    print(f"Saved PyTorch weights to: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
