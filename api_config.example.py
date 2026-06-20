"""
API keys / configuration for Merphi Audio Inspector.

Copy this file to `api_config.py` and paste your keys below
(or set them as environment variables, which take priority).
Leave a value as an empty string to DISABLE that integration.
"""

import os

# --- YouTube Data API v3 ---------------------------------------------------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# --- ACRCloud audio fingerprinting -----------------------------------------
ACR_HOST = os.environ.get("ACR_HOST", "identify-ap-southeast-1.acrcloud.com")
ACR_KEY = os.environ.get("ACR_KEY", "")
ACR_SECRET = os.environ.get("ACR_SECRET", "")

# --- Google Gemini ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def youtube_enabled() -> bool:
    return bool(YOUTUBE_API_KEY)


def acrcloud_enabled() -> bool:
    return bool(ACR_KEY and ACR_SECRET)


def gemini_enabled() -> bool:
    return bool(GEMINI_API_KEY)
