"""
Gemini-powered A&R report and editorial pitch generation.
"""

from __future__ import annotations

import json
from typing import Any

import api_config

_cached_model_name: str | None = None


def gemini_enabled() -> bool:
    return api_config.gemini_enabled()


def _ensure_client() -> None:
    """Configure google-generativeai with the API key before any model call."""
    if not gemini_enabled():
        raise RuntimeError("Gemini API key is not configured.")
    import google.generativeai as genai

    genai.configure(api_key=api_config.GEMINI_API_KEY)


def get_valid_model_name() -> str:
    """Pick the best available Gemini model from the API catalog."""
    global _cached_model_name
    if _cached_model_name:
        return _cached_model_name

    _ensure_client()
    import google.generativeai as genai

    valid_models = []
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            valid_models.append(m.name)

    for name in valid_models:
        if "gemini-1.5-flash" in name:
            _cached_model_name = name
            return name
    for name in valid_models:
        if "gemini-1.5-pro" in name:
            _cached_model_name = name
            return name
    for name in valid_models:
        if "gemini" in name:
            _cached_model_name = name
            return name

    _cached_model_name = valid_models[0] if valid_models else "gemini-1.5-flash"
    return _cached_model_name


def _format_track_data(track_data: dict[str, Any]) -> str:
    if isinstance(track_data, str):
        return track_data.strip()
    try:
        return json.dumps(track_data, ensure_ascii=False, indent=2)
    except TypeError:
        return str(track_data)


def _language_instruction(language_code: str) -> str:
    code = (language_code or "en").strip().lower()
    return (
        f"CRITICAL INSTRUCTION: You MUST write the entire response strictly in "
        f"the language corresponding to this language code: '{code}'."
    )


def _generate(prompt: str) -> str:
    _ensure_client()
    import google.generativeai as genai

    selected_model = get_valid_model_name()
    model = genai.GenerativeModel(selected_model)
    response = model.generate_content(prompt)
    text = getattr(response, "text", None) or ""
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response.")
    return text.strip()


def generate_ar_report(
    track_data: dict[str, Any] | str,
    language_code: str = "en",
) -> str:
    payload = _format_track_data(
        track_data if isinstance(track_data, dict) else {"query": track_data}
    )
    prompt = (
        "You are a lead A&R manager at Merphi Music Group. "
        f"Analyze this track: {payload}. "
        "Write a professional business report. "
        "Use exactly 4 sections with these emojis as section headers: "
        "🎯 OVERALL PRODUCT POTENTIAL, "
        "🌐 AUDIENCE FOCUS, "
        "⚡ STRENGTHS AND WEAKNESSES, "
        "📈 PROMOTION RECOMMENDATIONS. "
        "Be analytical and concise — no filler. "
        f"{_language_instruction(language_code)}"
    )
    return _generate(prompt)


def generate_editorial_pitch(
    track_data: dict[str, Any] | str,
    language_code: str = "en",
) -> str:
    payload = _format_track_data(
        track_data if isinstance(track_data, dict) else {"query": track_data}
    )
    prompt = (
        "You are a top music marketer. "
        "Write a pitch (description) for playlist curators "
        "(VK, Yandex Music, Spotify) for this track: "
        f"{payload}. "
        "Describe the atmosphere, vibe, and who will connect with it. "
        "You MUST NOT use dry technical terms or numbers "
        "(no BPM, hertz, energy percentages, or duration). "
        "The text must be vivid, engaging, emotional, and short "
        "(maximum 3-4 sentences). End with ISRC and genre. "
        f"{_language_instruction(language_code)}"
    )
    return _generate(prompt)
