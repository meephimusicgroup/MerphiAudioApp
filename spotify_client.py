"""
Spotify integration for Merphi Audio Inspector.

- Track search + Record Label + Release Date + Spotify URL  (works with the
  free Client Credentials flow).
- Audio features (BPM / Energy / Danceability / Mood):
  Spotify DEPRECATED the /audio-features endpoint on 2024-11-27. Apps in
  "Development mode" now receive HTTP 403 for it. So we attempt Spotify first
  and automatically fall back to a LOCAL analysis computed with librosa.

SECURITY NOTE
-------------
Hardcoding the client secret in source code is not recommended. The values
below are only defaults; you can (and should) override them with environment
variables SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET. Because this secret has
been shared, rotate it in the Spotify dashboard ("Rotate client secret").
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

# Provided by the user (override via environment variables in production).
DEFAULT_CLIENT_ID = "3fed3e694afc4523a5da0140377a9b18"
DEFAULT_CLIENT_SECRET = "8aaf7f706ae4431f8d99e114e54fed14"

# Filename noise removed before searching Spotify.
_NOISE_TOKENS = {
    "official", "video", "audio", "lyrics", "lyric", "hd", "hq", "4k",
    "visualizer", "visualiser", "mv", "m/v", "prod", "remaster", "remastered",
    "master", "free", "download", "mp3", "wav", "flac", "explicit", "clip",
}
_FEAT_RE = re.compile(r"\b(feat|ft|featuring|with)\b.*", re.IGNORECASE)
_BRACKETS_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")


def build_search_query(filepath: str | Path) -> str:
    """Build a clean 'artist title' query from metadata, falling back to filename."""
    filepath = Path(filepath)

    # Prefer embedded tags (title + artist) when available.
    try:
        from mutagen import File as MutagenFile

        tags = MutagenFile(str(filepath), easy=True)
        if tags:
            title = (tags.get("title") or [None])[0]
            artist = (tags.get("artist") or [None])[0]
            parts = [p for p in (artist, title) if p]
            if parts:
                return " ".join(parts).strip()
    except Exception:
        pass

    name = filepath.stem
    name = _BRACKETS_RE.sub(" ", name)
    name = _FEAT_RE.sub(" ", name)
    name = name.replace("_", " ").replace(".", " ").replace("-", " ")
    words = [w for w in name.split() if w.lower() not in _NOISE_TOKENS]
    cleaned = " ".join(words).strip()
    return cleaned or filepath.stem


class SpotifyInsights:
    """Singleton wrapper around spotipy + local audio feature fallback."""

    _instance: "SpotifyInsights | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._client = None
        self._client_error: str | None = None
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "SpotifyInsights":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # -- Spotify client -------------------------------------------------

    def _get_client(self):
        if self._client is not None or self._client_error is not None:
            return self._client

        with self._lock:
            if self._client is not None or self._client_error is not None:
                return self._client
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials

                client_id = os.environ.get("SPOTIPY_CLIENT_ID", DEFAULT_CLIENT_ID)
                client_secret = os.environ.get(
                    "SPOTIPY_CLIENT_SECRET", DEFAULT_CLIENT_SECRET
                )
                auth = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                    # Without this the initial OAuth token POST can block forever.
                    requests_timeout=10,
                )
                # retries/status_retries=0: never auto-sleep on HTTP 429.
                # (Spotify can send Retry-After of hours, which would freeze the
                #  worker thread; we surface a rate-limit message instead.)
                self._client = spotipy.Spotify(
                    client_credentials_manager=auth,
                    requests_timeout=10,
                    retries=0,
                    status_retries=0,
                    backoff_factor=0,
                )
            except Exception as exc:
                self._client_error = str(exc)
                self._client = None
        return self._client

    # -- Public API -----------------------------------------------------

    @staticmethod
    def _empty_result(query: str) -> dict:
        return {
            "query": query,
            "found": False,
            "label": None,
            "release_date": None,
            "url": None,
            "matched_name": None,
            "popularity": None,
            "isrc": None,
            "upc": None,
            "distributor": None,
            "cover_url": None,
            "cover_bytes": None,
            "source": "text",
            "error": None,
        }

    def _fill_from_track(self, client, track: dict, result: dict) -> None:
        result["found"] = True
        result["matched_name"] = _format_track_name(track)
        result["url"] = track.get("external_urls", {}).get("spotify")
        result["popularity"] = track.get("popularity")
        result["isrc"] = (track.get("external_ids") or {}).get("isrc")

        album = track.get("album", {})
        result["release_date"] = album.get("release_date")

        images = album.get("images") or []
        if images:
            result["cover_url"] = _best_cover_url(images)

        album_id = album.get("id")
        if album_id:
            try:
                full_album = client.album(album_id)
                copyrights = full_album.get("copyrights")
                label = full_album.get("label")
                if not label:
                    label = _label_from_copyrights(copyrights)
                result["label"] = label or None
                result["upc"] = (full_album.get("external_ids") or {}).get("upc")
                result["distributor"] = _detect_distributor(copyrights, label)
                album_images = full_album.get("images") or []
                if album_images:
                    result["cover_url"] = _best_cover_url(album_images)
            except Exception:
                pass

        if result["cover_url"]:
            result["cover_bytes"] = _fetch_image_bytes(result["cover_url"])

    def _run_search(self, query: str, spotify_query: str) -> dict:
        result = self._empty_result(query)
        client = self._get_client()
        if client is None:
            result["error"] = self._client_error or "Spotify client unavailable"
            return result
        try:
            search = client.search(q=spotify_query, type="track", limit=1)
            items = search.get("tracks", {}).get("items", [])
            if items:
                self._fill_from_track(client, items[0], result)
        except Exception as exc:
            if getattr(exc, "http_status", None) == 429:
                result["error"] = "rate_limited"
            else:
                result["error"] = str(exc)
        return result

    def search_metadata(self, filepath: str | Path) -> dict:
        """Text-based Spotify lookup from the filename/tags."""
        query = build_search_query(filepath)
        return self._run_search(query, query)

    def search_by_isrc(self, isrc: str, display_query: str = "") -> dict:
        """Exact Spotify lookup by ISRC (used after an ACRCloud match)."""
        result = self._run_search(display_query or isrc, f"isrc:{isrc}")
        result["source"] = "acrcloud"
        return result

    def local_features(self, filepath: str | Path) -> dict | None:
        """Compute BPM / Energy / Danceability / Mood locally (librosa)."""
        return compute_local_features(filepath)

    def analyze(self, filepath: str | Path) -> dict:
        """Convenience: metadata + local features in one call."""
        result = self.search_metadata(filepath)
        result["features"] = self.local_features(filepath)
        return result


# ---------------------------------------------------------------------------
# Local audio feature estimation (librosa fallback)
# ---------------------------------------------------------------------------

# Krumhansl-Schmuckler key profiles for major/minor estimation.
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Camelot wheel codes by root pitch class.
_CAMELOT_MAJOR = {0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
                  6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B"}
_CAMELOT_MINOR = {0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
                  6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A"}


def _label_from_copyrights(copyrights) -> str | None:
    """Derive a label/distributor name from album copyright (℗/©) lines."""
    if not copyrights:
        return None
    for entry in copyrights:
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        # Strip a leading copyright marker (℗ © or "(C)"/"(P)") and an optional year.
        cleaned = re.sub(
            r"^\s*(?:[\u2117\u00a9]\s*|\([cCpP]\)\s*)?(?:\d{4}\s+)?",
            "",
            text,
        ).strip()
        return cleaned or text
    return None


# Known music distributors (Spotify has no dedicated field; inferred from text).
_DISTRIBUTORS = {
    "distrokid": "DistroKid",
    "tunecore": "TuneCore",
    "cd baby": "CD Baby",
    "cdbaby": "CD Baby",
    "believe": "Believe",
    "the orchard": "The Orchard",
    "orchard": "The Orchard",
    "awal": "AWAL",
    "onerpm": "ONErpm",
    "one rpm": "ONErpm",
    "ditto": "Ditto Music",
    "amuse": "Amuse",
    "symphonic": "Symphonic Distribution",
    "fuga": "FUGA",
    "unitedmasters": "UnitedMasters",
    "united masters": "UnitedMasters",
    "routenote": "RouteNote",
    "repost": "Repost Network",
    "soundrop": "Soundrop",
    "stem": "Stem",
    "empire": "EMPIRE",
    "ingrooves": "Ingrooves",
    "too lost": "Too Lost",
    "toolost": "Too Lost",
    "label engine": "Label Engine",
    "horus": "Horus Music",
}


def _detect_distributor(copyrights, label: str | None) -> str | None:
    haystack_parts = []
    if copyrights:
        for entry in copyrights:
            haystack_parts.append((entry.get("text") or ""))
    if label:
        haystack_parts.append(label)
    haystack = " ".join(haystack_parts).lower()
    for needle, canonical in _DISTRIBUTORS.items():
        if needle in haystack:
            return canonical
    return None


def _best_cover_url(images: list) -> str | None:
    """Pick the highest-resolution album art URL (Spotify lists largest first)."""
    if not images:
        return None

    def _area(img: dict) -> int:
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        return w * h if w and h else 0

    ranked = sorted(images, key=_area, reverse=True)
    for img in ranked:
        url = img.get("url")
        if url:
            return url
    return images[0].get("url")


def _fetch_image_bytes(url: str, timeout: int = 12) -> bytes | None:
    try:
        import urllib.request

        req = urllib.request.Request(
            url, headers={"User-Agent": "MerphiAudioInspector/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def compute_local_features(filepath: str | Path) -> dict | None:
    """Estimate BPM / energy / danceability / valence locally with librosa."""
    try:
        import warnings

        import librosa
        import numpy as np

        # Analyse up to 45s for speed; mono is enough for these features.
        y, sr = librosa.load(str(filepath), sr=22050, mono=True, duration=45.0)
        if y.size == 0:
            return None

        # --- Tempo (BPM) ---
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                import librosa.feature.rhythm as _rhythm  # librosa >= 0.10

                tempo = _rhythm.tempo(onset_envelope=onset_env, sr=sr)
            except Exception:
                tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0]) if tempo is not None else 0.0

        # --- Energy (loudness-based proxy, 0..1) ---
        rms = librosa.feature.rms(y=y)[0]
        rms_db = librosa.amplitude_to_db(rms + 1e-10, ref=1.0)
        energy = float(np.clip((np.mean(rms_db) + 60.0) / 60.0, 0.0, 1.0))

        # --- Danceability (beat clarity + danceable tempo range) ---
        try:
            plp = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
            pulse_score = float(np.clip(np.mean(plp) * 3.0, 0.0, 1.0))
        except Exception:
            pulse_score = 0.5
        tempo_score = float(np.exp(-((bpm - 120.0) ** 2) / (2 * 40.0 ** 2)))
        danceability = float(np.clip(0.5 * pulse_score + 0.5 * tempo_score, 0.0, 1.0))

        # --- Key / Camelot + valence (major-minor + brightness heuristic) ---
        key_name, camelot, valence = _estimate_key_valence(y, sr, np, librosa)

        return {
            "bpm": round(bpm),
            "energy": energy,
            "danceability": danceability,
            "valence": valence,
            "valence_positive": valence >= 0.5,
            "key": key_name,
            "camelot": camelot,
            "source": "local",
        }
    except Exception:
        return None


def _estimate_key_valence(y, sr, np, librosa):
    """Return (key_name, camelot_code, valence) via Krumhansl key detection."""
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        major = np.array(_MAJOR_PROFILE)
        minor = np.array(_MINOR_PROFILE)

        best_corr, best_root, best_mode = -2.0, 0, "major"
        for i in range(12):
            cm = np.corrcoef(np.roll(major, i), chroma_mean)[0, 1]
            if cm > best_corr:
                best_corr, best_root, best_mode = cm, i, "major"
            cn = np.corrcoef(np.roll(minor, i), chroma_mean)[0, 1]
            if cn > best_corr:
                best_corr, best_root, best_mode = cn, i, "minor"

        key_name = f"{_NOTE_NAMES[best_root]} {best_mode}"
        camelot = (_CAMELOT_MAJOR if best_mode == "major" else _CAMELOT_MINOR)[best_root]

        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        brightness = float(np.clip(centroid / (sr / 4.0), 0.0, 1.0))
        valence = 0.5 + (0.18 if best_mode == "major" else -0.18) + (brightness - 0.5) * 0.4

        return key_name, camelot, float(np.clip(valence, 0.0, 1.0))
    except Exception:
        return None, None, 0.5


def _format_track_name(track: dict) -> str:
    artists = ", ".join(a.get("name", "") for a in track.get("artists", []) if a)
    name = track.get("name", "")
    return f"{artists} — {name}".strip(" —") if artists else name
