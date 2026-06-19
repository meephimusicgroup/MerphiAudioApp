"""Configuration loader (adapted from deezer/deepfake-detector)."""

from __future__ import annotations

import json
from pathlib import Path


class ConfLoader:
    def __init__(self, path: Path, base_name: str = "base") -> None:
        self.path = path
        with open(self.path / f"{base_name}.json", encoding="utf-8") as handle:
            self.base = json.load(handle)
        self.model: dict = {}
        self.self_update()

    def load_model(self, model_name: str) -> None:
        model_path = self.path / f"{model_name}.json"
        if not model_path.is_file():
            raise ValueError(f"Model config not found: {model_path}")
        with open(model_path, encoding="utf-8") as handle:
            self.model = json.load(handle)
        self.self_update()

    def self_update(self) -> None:
        conf: dict = {}
        conf.update(self.base)
        conf.update(self.model)
        self.conf = conf
