"""
Apple Music / iTunes Search API — high-resolution artwork (no API key required).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

_ITUNES_SEARCH = "https://itunes.apple.com/search"
_ARTWORK_SIZE_RE = re.compile(r"\d+x\d+bb\.(jpg|png)", re.IGNORECASE)


def _upscale_artwork_url(url: str) -> str:
    """Upgrade iTunes artwork URL to 3000×3000 (Apple CDN serves the original)."""
    if not url:
        return url
    return _ARTWORK_SIZE_RE.sub("3000x3000bb.\\1", url)


def search_hi_res_artwork_url(artist: str, track: str) -> str | None:
    """
    Search iTunes for a song and return a 3000×3000 artwork URL, or None.
    """
    term = " ".join(p for p in (artist, track) if p and p != "—").strip()
    if not term:
        return None

    params = urllib.parse.urlencode(
        {"term": term, "entity": "song", "limit": 1},
        quote_via=urllib.parse.quote,
    )
    api_url = f"{_ITUNES_SEARCH}?{params}"
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "MerphiAudioInspector/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    results = payload.get("results") or []
    if not results:
        return None

    artwork = results[0].get("artworkUrl100") or results[0].get("artworkUrl60")
    if not artwork:
        return None

    return _upscale_artwork_url(artwork)


def download_artwork(url: str, timeout: int = 30) -> bytes | None:
    """Download artwork bytes from a CDN URL."""
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "MerphiAudioInspector/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None
