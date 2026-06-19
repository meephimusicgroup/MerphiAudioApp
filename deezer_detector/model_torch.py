"""PyTorch port of Deezer SimpleSpectrogramCNN (specnn_amplitude)."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class Swish(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(x)


class DeezerSpecCNN(nn.Module):
    """Matches deezer/deepfake-detector model/simple_cnn.py SimpleSpectrogramCNN."""

    def __init__(self) -> None:
        super().__init__()
        channels = [16, 32, 64, 128, 256, 512]

        blocks: list[nn.Module] = []
        in_channels = 1
        for out_channels in channels:
            blocks.extend(
                [
                    nn.Conv2d(
                        in_channels,
                        out_channels,
                        kernel_size=3,
                        stride=1,
                        padding=1,
                        bias=True,
                    ),
                    nn.ReLU(inplace=True),
                    nn.MaxPool2d(kernel_size=2, stride=2, padding=0),
                    nn.BatchNorm2d(out_channels, eps=0.001, momentum=0.01),
                ]
            )
            in_channels = out_channels

        self.features = nn.Sequential(*blocks)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(512, 128),
            Swish(),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.pool(x)
        return torch.sigmoid(self.head(x))

    def predict_deepfake_probability(self, x: torch.Tensor) -> float:
        self.eval()
        with torch.no_grad():
            return float(self.forward(x).reshape(-1)[0].item())
