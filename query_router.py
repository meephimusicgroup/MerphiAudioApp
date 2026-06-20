"""
Smart Search query classification and routing for Merphi Audio Inspector.
"""

from __future__ import annotations

import re

from spotify_client import SpotifyInsights, extract_spotify_track_id
from youtube_client import YouTubeClient, extract_youtube_video_id

ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$", re.IGNORECASE)
UPC_RE = re.compile(r"^\d{12,13}$")


def normalize_isrc(value: str) -> str:
    return value.strip().upper().replace("-", "").replace(" ", "")


def classify_query(text: str) -> str:
    """Return query type: spotify_link, youtube_link, isrc, upc, or text."""
    raw = text.strip()
    if not raw:
        return "empty"
    if extract_spotify_track_id(raw):
        return "spotify_link"
    if extract_youtube_video_id(raw):
        return "youtube_link"
    if ISRC_RE.match(normalize_isrc(raw)):
        return "isrc"
    if UPC_RE.match(raw):
        return "upc"
    return "text"


def route_smart_query(text: str) -> dict:
    """
    Resolve a Smart Search string to Spotify + YouTube metadata bundles.
    """
    raw = text.strip()
    query_type = classify_query(raw)
    insights = SpotifyInsights.get()
    yt_enabled = YouTubeClient.enabled()
    yt_client = YouTubeClient.get() if yt_enabled else None

    def _youtube_for(query: str | None):
        if not yt_client or not query:
            return None
        return yt_client.fetch(query)

    if query_type == "empty":
        return {
            "query": raw,
            "query_type": query_type,
            "spotify": insights._empty_result(raw),
            "youtube": None,
        }

    if query_type == "spotify_link":
        track_id = extract_spotify_track_id(raw)
        spotify = insights.search_by_track_id(track_id or raw)
        youtube = _youtube_for(spotify.get("matched_name") or raw)
        return {
            "query": raw,
            "query_type": query_type,
            "spotify": spotify,
            "youtube": youtube,
        }

    if query_type == "youtube_link":
        video_id = extract_youtube_video_id(raw)
        youtube = (
            yt_client.fetch_by_video_id(video_id)
            if yt_client and video_id
            else None
        )
        sp_query = (youtube or {}).get("title") or raw
        spotify = insights.search_by_text(sp_query)
        return {
            "query": raw,
            "query_type": query_type,
            "spotify": spotify,
            "youtube": youtube,
        }

    if query_type == "isrc":
        isrc = normalize_isrc(raw)
        spotify = insights.search_by_isrc(isrc, isrc, source="isrc")
        youtube = _youtube_for(spotify.get("matched_name") or isrc)
        return {
            "query": raw,
            "query_type": query_type,
            "spotify": spotify,
            "youtube": youtube,
        }

    if query_type == "upc":
        upc = raw.strip()
        spotify = insights.search_by_upc(upc)
        youtube = _youtube_for(spotify.get("matched_name") or upc)
        return {
            "query": raw,
            "query_type": query_type,
            "spotify": spotify,
            "youtube": youtube,
        }

    spotify = insights.search_by_text(raw)
    youtube = _youtube_for(spotify.get("matched_name") or raw)
    return {
        "query": raw,
        "query_type": "text",
        "spotify": spotify,
        "youtube": youtube,
    }
