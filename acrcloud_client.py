"""
ACRCloud audio fingerprinting (identify a track from a short audio sample).

Implemented with `requests` + HMAC-SHA1 signing (no native SDK needed, so it
works on any Python version). Sends a ~10s PCM sample to the ACRCloud
identify endpoint and returns normalized metadata.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import threading
import time
from pathlib import Path

import api_config


class ACRCloudClient:
    _instance: "ACRCloudClient | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "ACRCloudClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def enabled() -> bool:
        return api_config.acrcloud_enabled()

    def _extract_sample(self, filepath: str | Path, seconds: int = 12) -> bytes | None:
        """Return a mono 16-bit PCM WAV sample (~`seconds`) as bytes."""
        try:
            import librosa
            import soundfile as sf

            total = 0.0
            try:
                total = float(librosa.get_duration(path=str(filepath)))
            except Exception:
                total = 0.0

            # Start a bit into the track (skip intros) when it's long enough.
            offset = 20.0 if total > 40.0 else 0.0
            y, sr = librosa.load(
                str(filepath), sr=44100, mono=True, offset=offset, duration=seconds
            )
            if y.size == 0:
                y, sr = librosa.load(str(filepath), sr=44100, mono=True, duration=seconds)
            if y.size == 0:
                return None

            buf = io.BytesIO()
            sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
            return buf.getvalue()
        except Exception:
            return None

    def identify(self, filepath: str | Path) -> dict:
        """
        Returns:
            {enabled, matched, title, artist, isrc, upc, label, album,
             spotify_id, error}
        """
        result = {
            "enabled": self.enabled(),
            "matched": False,
            "title": None,
            "artist": None,
            "isrc": None,
            "upc": None,
            "label": None,
            "album": None,
            "spotify_id": None,
            "error": None,
        }
        if not self.enabled():
            return result

        sample = self._extract_sample(filepath)
        if not sample:
            result["error"] = "Could not read audio sample"
            return result

        try:
            import requests

            http_method = "POST"
            http_uri = "/v1/identify"
            data_type = "audio"
            signature_version = "1"
            timestamp = str(time.time())

            string_to_sign = "\n".join([
                http_method, http_uri, api_config.ACR_KEY,
                data_type, signature_version, timestamp,
            ])
            signature = base64.b64encode(
                hmac.new(
                    api_config.ACR_SECRET.encode("ascii"),
                    string_to_sign.encode("ascii"),
                    digestmod=hashlib.sha1,
                ).digest()
            ).decode("ascii")

            files = {"sample": ("sample.wav", sample, "audio/wav")}
            data = {
                "access_key": api_config.ACR_KEY,
                "sample_bytes": str(len(sample)),
                "timestamp": timestamp,
                "signature": signature,
                "data_type": data_type,
                "signature_version": signature_version,
            }
            url = f"https://{api_config.ACR_HOST}{http_uri}"
            response = requests.post(url, files=files, data=data, timeout=20)
            payload = response.json()
        except Exception as exc:
            result["error"] = str(exc)
            return result

        status = payload.get("status", {})
        if status.get("code") != 0:
            # 1001 = no result; other codes = real errors.
            if status.get("code") != 1001:
                result["error"] = status.get("msg") or f"ACR code {status.get('code')}"
            return result

        music_list = (payload.get("metadata") or {}).get("music") or []
        if not music_list:
            return result

        music = music_list[0]
        result["matched"] = True
        result["title"] = music.get("title")
        artists = music.get("artists") or []
        result["artist"] = ", ".join(a.get("name", "") for a in artists if a) or None
        ext_ids = music.get("external_ids") or {}
        result["isrc"] = ext_ids.get("isrc") or None
        result["upc"] = ext_ids.get("upc") or None
        result["label"] = music.get("label") or None
        result["album"] = (music.get("album") or {}).get("name") or None
        spotify = (music.get("external_metadata") or {}).get("spotify") or {}
        result["spotify_id"] = (spotify.get("track") or {}).get("id")
        return result
