"""
YouTube Data API v3 lookup: find the most relevant video for a track and
return views, channel name, upload date, description-derived credits, and URL.
"""

from __future__ import annotations

import re
import threading

import api_config

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

_PROVIDED_BY = "Provided to YouTube by "
_BULLET_SEP = " • "
_CREDIT_PATTERNS = (
    re.compile(r"Producer:\s*(.+)", re.IGNORECASE),
    re.compile(r"Composer:\s*(.+)", re.IGNORECASE),
    re.compile(r"Lyricist:\s*(.+)", re.IGNORECASE),
)


def _extract_art_track_writers(description: str) -> list[str]:
    """
    YouTube Art Tracks often list real names on a bullet-separated line:
    "Title • Artist • Writer One • Writer Two"
    """
    writers: list[str] = []
    seen: set[str] = set()

    for raw_line in description.splitlines():
        line = raw_line.strip()
        if line.count(_BULLET_SEP) < 2:
            continue
        parts = [p.strip() for p in line.split(_BULLET_SEP) if p.strip()]
        if len(parts) < 3:
            continue
        for name in parts[1:]:
            if name and name not in seen:
                seen.add(name)
                writers.append(name)

    return writers


def parse_youtube_description(description: str | None) -> dict:
    """Extract distributor, credit lines, and Art Track writer names."""
    result = {"distributor": None, "credits": [], "writers": []}
    if not description:
        return result

    if _PROVIDED_BY in description:
        start = description.index(_PROVIDED_BY) + len(_PROVIDED_BY)
        end = description.find("\n", start)
        if end == -1:
            end = len(description)
        distributor = description[start:end].strip()
        if distributor:
            result["distributor"] = distributor

    seen: set[str] = set()
    for pattern in _CREDIT_PATTERNS:
        for match in pattern.finditer(description):
            line = match.group(0).strip()
            line = line.split("\n")[0].strip()
            if line and line not in seen:
                seen.add(line)
                result["credits"].append(line)

    result["writers"] = _extract_art_track_writers(description)
    return result


class YouTubeClient:
    _instance: "YouTubeClient | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "YouTubeClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def enabled() -> bool:
        return api_config.youtube_enabled()

    def fetch(self, query: str) -> dict:
        """
        Returns:
            {enabled, found, title, channel, published, views, url,
             description, distributor, credits, error}
        """
        result = {
            "enabled": self.enabled(),
            "found": False,
            "title": None,
            "channel": None,
            "published": None,
            "views": None,
            "url": None,
            "description": None,
            "distributor": None,
            "credits": [],
            "writers": [],
            "error": None,
        }
        if not self.enabled() or not query:
            return result

        try:
            import requests

            key = api_config.YOUTUBE_API_KEY
            search_params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": key,
            }
            sr = requests.get(_SEARCH_URL, params=search_params, timeout=15)
            sdata = sr.json()
            if "error" in sdata:
                result["error"] = sdata["error"].get("message", "YouTube API error")
                return result

            items = sdata.get("items") or []
            if not items:
                return result

            item = items[0]
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            result["found"] = True
            result["title"] = snippet.get("title")
            result["channel"] = snippet.get("channelTitle")
            result["published"] = (snippet.get("publishedAt") or "")[:10] or None
            if video_id:
                result["url"] = f"https://www.youtube.com/watch?v={video_id}"

            if video_id:
                vr = requests.get(
                    _VIDEOS_URL,
                    params={"part": "snippet,statistics", "id": video_id, "key": key},
                    timeout=15,
                )
                vdata = vr.json()
                vitems = vdata.get("items") or []
                if vitems:
                    full_snippet = vitems[0].get("snippet") or {}
                    stats = vitems[0].get("statistics") or {}
                    description = full_snippet.get("description") or ""
                    result["description"] = description
                    parsed = parse_youtube_description(description)
                    result["distributor"] = parsed["distributor"]
                    result["credits"] = parsed["credits"]
                    result["writers"] = parsed["writers"]
                    views = stats.get("viewCount")
                    result["views"] = int(views) if views is not None else None
        except Exception as exc:
            result["error"] = str(exc)

        return result


def format_views(views) -> str:
    """Human-readable view count (e.g. 1.2M, 34.5K)."""
    if views is None:
        return ""
    try:
        n = int(views)
    except (TypeError, ValueError):
        return str(views)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
