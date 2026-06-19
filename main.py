"""
Merphi Audio Inspector
A modern Windows desktop tool for inspecting audio file specifications
and local Deezer deepfake-detector AI music analysis.
"""

APP_VERSION = "1.0.0"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/merphimusic/updates/main/version.json"

import json
import os
import re
import socket
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
import configparser
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from mutagen import File as MutagenFile
from pymediainfo import MediaInfo

from deezer_detector import DeezerDeepfakeDetector, ModelNotReadyError
from spotify_client import SpotifyInsights, build_search_query
from acrcloud_client import ACRCloudClient
from youtube_client import YouTubeClient, format_views
from apple_music_client import search_hi_res_artwork_url, download_artwork

try:
    from CTkMessagebox import CTkMessagebox

    CTKMESSAGEBOX_AVAILABLE = True
except ImportError:
    CTKMESSAGEBOX_AVAILABLE = False

try:
    import windnd

    WINDND_AVAILABLE = True
except ImportError:
    WINDND_AVAILABLE = False

try:
    import pywinstyles

    PYWINSTYLES_AVAILABLE = True
except ImportError:
    PYWINSTYLES_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from pydub import AudioSegment

# Determine absolute path to the project root (handles both script and PyInstaller .exe execution)
if getattr(sys, "frozen", False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

ffmpeg_path = os.path.join(application_path, "ffmpeg.exe")
icon_path = os.path.join(application_path, "icon.ico")
AudioSegment.converter = ffmpeg_path
AudioSegment.ffmpeg = ffmpeg_path


# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac"}
WINDOW_SIZE = "980x920"
CONTENT_PADX = 32
PANEL_GAP = 16
MAX_CONTENT_WIDTH = 900

SPEC_COLUMNS = (
    ("file_name", "format", "codec"),
    ("bit_depth", "sampling_rate", "channels"),
    ("bitrate", "duration", "daw_encoder"),
)
DEMO_FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSd8VknH-Dwixy-cSu0fwGyQjlenDtzP-3PQC3o58Wt7-lgYNQ/viewform"
)
ABOUT_WEBSITE_URL = "https://merphimusic.com"
ABOUT_SMARTLINK_URL = "https://merphimusic.lnk.to/mmg"
MMG_LABEL_MARKER = "merphi music group"
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Merphi Audio Inspector"
CONFIG_PATH = CONFIG_DIR / "config.ini"
INSTALLER_LANG_MAP = {
    "russian": "ru",
    "english": "en",
    "ru": "ru",
    "en": "en",
}

# Liquid-glass palette — root CTk must stay solid; inner frames use "transparent".
COLOR_BG = "#f4f4f6"
COLOR_SURFACE = "#ffffff"
COLOR_SURFACE_ALT = "#f0f0f3"
COLOR_BORDER = "#e2e2e8"
COLOR_TEXT = "#1a1a22"
COLOR_MUTED = "#6b6b78"
COLOR_ACCENT = "#7c3aed"
COLOR_ACCENT_HOVER = "#6d28d9"
COLOR_SUCCESS = "#15803d"
COLOR_WARNING = "#b45309"
COLOR_DEMO = "#111827"
COLOR_DEMO_HOVER = "#1f2937"
COLOR_SPOTIFY = "#1db954"
COLOR_SPOTIFY_HOVER = "#1ed760"
COLOR_YOUTUBE = "#c4302b"
COLOR_YOUTUBE_HOVER = "#e0392f"
COLOR_CARD_INNER = "#f5f5f8"
LOGO_DISPLAY_SIZE = 88
COVER_DISPLAY_SIZE = 128

LANGUAGE_OPTIONS = {
    "English": "en",
    "Русский": "ru",
    "日本語": "ja",
    "中文": "zh",
    "Português": "pt",
    "Español": "es",
}
DEFAULT_LANGUAGE_LABEL = "Русский"

SPEC_KEYS = [
    "file_name",
    "format",
    "codec",
    "bit_depth",
    "sampling_rate",
    "channels",
    "bitrate",
    "duration",
    "daw_encoder",
]

SOFTWARE_TAG_HINTS = (
    "encoded",
    "encoder",
    "software",
    "originator",
    "tool",
    "daw",
    "tenc",
    "tsse",
    "tsof",
    "isft",
    "application",
    "writing",
    "product",
)

# Known DAWs / audio editors, prioritised when several hints are found.
KNOWN_DAWS = (
    "ableton", "live", "fl studio", "fruity", "image-line", "logic",
    "cubase", "nuendo", "pro tools", "protools", "reaper", "studio one",
    "bitwig", "garageband", "audition", "audacity", "reason", "cakewalk",
    "sonar", "ardour", "mixcraft", "sound forge", "soundforge", "wavelab",
    "samplitude", "renoise", "maschine", "serato", "acid pro",
)

TRANSLATIONS = {
    "en": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "A product by Merphi Music Group",
        "drop_primary": "Drag & drop an audio file here",
        "drop_hint": "Supported formats: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "No file loaded",
        "file_loaded_success": "File loaded successfully",
        "browse_button": "Browse for file",
        "specs_header": "Technical Specifications",
        "spec_file_name": "File name",
        "spec_format": "Format",
        "spec_codec": "Codec",
        "spec_bit_depth": "Bit depth",
        "spec_sampling_rate": "Sampling rate",
        "spec_channels": "Channels",
        "spec_bitrate": "Bitrate",
        "spec_duration": "Duration",
        "spec_daw_encoder": "DAW / Encoder",
        "analyze_button": "🔍 Analyze with AI",
        "ai_idle": "Load a file, then run AI analysis.",
        "ai_ready": "Ready for AI analysis.",
        "ai_complete": "Analysis complete.",
        "progress_scanning": "Scanning audio fingerprint...",
        "progress_spectral": "Analyzing spectral patterns...",
        "progress_artifacts": "Checking generative artifacts...",
        "progress_comparing": "Comparing against model signatures...",
        "progress_finalizing": "Finalizing confidence score...",
        "ai_result": "Probability of AI generation: {probability}% - {verdict}",
        "verdict_human": "Human",
        "verdict_ai": "AI",
        "progress_loading_model": "Loading Deezer detection model...",
        "progress_running_model": "Running Deezer deepfake analysis...",
        "msg_model_missing_title": "Model not downloaded",
        "msg_model_missing_body": "Deezer PyTorch weights are missing.\n\nRun in the project folder:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "AI analysis failed",
        "msg_ai_error_body": "Could not complete AI analysis.\n\n{error}",
        "demo_button": "Submit Demo to Merphi Music Group",
        "spotify_header": "Spotify Insights",
        "spotify_idle": "Load a file to look it up on Spotify.",
        "spotify_searching": "Searching on Spotify...",
        "spotify_found": "Found: {name}",
        "spotify_not_found": "Unreleased Demo / Not Found",
        "spotify_label": "Record Label",
        "spotify_release": "Release Date",
        "spotify_mood": "Mood / Vibe",
        "spotify_bpm": "BPM / Tempo",
        "spotify_energy": "Energy",
        "spotify_danceability": "Danceability",
        "spotify_popularity": "Popularity",
        "spotify_key": "Key / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "Distributor",
        "credits_artist": "Artist",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 Editorial description",
        "btn_youtube": "▶️ Search on YouTube",
        "offline_warning": (
            "⚠️ No internet. Only local AI analysis and audio converter are available."
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 Wow, you're a true fan! Awesome that this track was released on "
            "Merphi Music Group!"
        ),
        "copy_button": "Copy",
        "copied": "Copied!",
        "close_button": "Close",
        "songdna_title": "Song DNA — Credits & Analysis",
        "desc_title": "Editorial description for streaming editors",
        "youtube_views": "YouTube views",
        "youtube_channel": "YouTube channel",
        "youtube_published": "Uploaded",
        "spotify_found_acr": "Matched via ACRCloud: {name}",
        "text_search_fallback": (
            "⚠️ Text Search Fallback: Results may be inaccurate for niche/underground tracks."
        ),
        "songdna_section_credits": "Credits (YouTube)",
        "songdna_section_writers": "Writers/Creators (YouTube)",
        "youtube_distributor": "YouTube Distributor",
        "credits_note": "Note: Deep credits (Producers/Songwriters) are restricted by public streaming APIs.",
        "spotify_open_btn": "Open in Spotify",
        "mood_positive": "Positive / Bright",
        "mood_dark": "Dark / Melancholic",
        "spotify_source_local": "local analysis",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Spotify audio features are deprecated — BPM/Energy/Mood come from local analysis.",
        "spotify_error": "Spotify lookup failed.",
        "spotify_rate_limited": "Spotify rate limit reached — try again later (local analysis still works).",
        "na": "N/A",
        "unit_bit": "bit",
        "unit_channel": "channel",
        "unit_channels": "channels",
        "unknown": "Unknown",
        "msg_unsupported_title": "Unsupported file",
        "msg_unsupported_body": "Please choose a supported audio file:\n{extensions}",
        "msg_not_found_title": "File not found",
        "msg_not_found_body": "That file could not be found.",
        "msg_mediainfo_title": "MediaInfo error",
        "msg_mediainfo_body": "Could not read file metadata.\n\n{error}\n\nMake sure MediaInfo is installed on your system.",
        "msg_no_file_title": "No file loaded",
        "msg_no_file_body": "Please load an audio file before running AI analysis.",
        "file_dialog_title": "Select an audio file",
        "file_dialog_audio": "Audio files",
        "file_dialog_wav": "WAV files",
        "file_dialog_mp3": "MP3 files",
        "file_dialog_flac": "FLAC files",
        "file_dialog_all": "All files",
        "audio_tools_header": "Audio Tools",
        "convert_format_label": "Target format",
        "convert_button": "Convert & Save",
        "convert_success_title": "Conversion complete",
        "convert_success_body": "Saved to:\n{path}",
        "convert_error_title": "Conversion failed",
        "convert_error_body": "Could not convert the file.\n\n{error}",
        "convert_ffmpeg_error": (
            "ffmpeg is required for audio conversion.\n\n"
            "Install ffmpeg and add it to your PATH, then try again.\n"
            "Download: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "Download High-Res Cover",
        "cover_saved_title": "Cover saved",
        "cover_saved_body": "Saved to:\n{path}",
        "cover_no_url": "No cover art URL available for this track.",
        "cover_error_title": "Download failed",
        "cover_error_body": "Could not download cover art.\n\n{error}",
        "songdna_section_release": "Release",
        "songdna_section_track": "Track Details",
        "songdna_section_identifiers": "Identifiers",
        "songdna_section_analytics": "Audio Analytics",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "Track",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "Listen to the release",
        "pitch_editor_keys": "Keys for editors",
        "card_file_title": "File & Technical Specs",
        "card_action_title": "Action Center",
        "about_btn": "About Us",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Merphi Music Group was founded by Artur Martemyanov at age 14 "
            "in Kangalassy (Yakutsk)."
        ),
        "about_website_btn": "Website: merphimusic.com",
        "about_smartlink_btn": "Smartlink: merphimusic.lnk.to/mmg",
    },
    "ru": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "Продукт Merphi Music Group",
        "drop_primary": "Перетащите аудиофайл сюда",
        "drop_hint": "Поддерживаемые форматы: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "Файл не загружен",
        "file_loaded_success": "Файл успешно загружен",
        "browse_button": "Выбрать файл",
        "specs_header": "Технические характеристики",
        "spec_file_name": "Имя файла",
        "spec_format": "Формат",
        "spec_codec": "Кодек",
        "spec_bit_depth": "Битность",
        "spec_sampling_rate": "Частота дискретизации",
        "spec_channels": "Каналы",
        "spec_bitrate": "Битрейт",
        "spec_duration": "Длительность",
        "spec_daw_encoder": "DAW / Кодировщик",
        "analyze_button": "🔍 Анализ с ИИ",
        "ai_idle": "Загрузите файл, затем запустите ИИ-анализ.",
        "ai_ready": "Готово к ИИ-анализу.",
        "ai_complete": "Анализ завершён.",
        "progress_scanning": "Сканирование аудиоотпечатка...",
        "progress_spectral": "Анализ спектральных паттернов...",
        "progress_artifacts": "Проверка артефактов генерации...",
        "progress_comparing": "Сравнение с сигнатурами моделей...",
        "progress_finalizing": "Финальный расчёт уверенности...",
        "ai_result": "Вероятность ИИ-генерации: {probability}% - {verdict}",
        "verdict_human": "Человек",
        "verdict_ai": "ИИ",
        "progress_loading_model": "Загрузка модели Deezer...",
        "progress_running_model": "Анализ Deezer deepfake...",
        "msg_model_missing_title": "Модель не загружена",
        "msg_model_missing_body": "Отсутствуют PyTorch-веса Deezer.\n\nВыполните в папке проекта:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "Ошибка ИИ-анализа",
        "msg_ai_error_body": "Не удалось выполнить ИИ-анализ.\n\n{error}",
        "demo_button": "Отправить демо в Merphi Music Group",
        "spotify_header": "Spotify-аналитика",
        "spotify_idle": "Загрузите файл для поиска в Spotify.",
        "spotify_searching": "Поиск в Spotify...",
        "spotify_found": "Найдено: {name}",
        "spotify_not_found": "Неизданное демо / Не найдено",
        "spotify_label": "Лейбл",
        "spotify_release": "Дата релиза",
        "spotify_mood": "Настроение / Вайб",
        "spotify_bpm": "BPM / Темп",
        "spotify_energy": "Энергия",
        "spotify_danceability": "Танцевальность",
        "spotify_popularity": "Популярность",
        "spotify_key": "Тональность / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "Дистрибьютор",
        "credits_artist": "Артист",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 Описание для редакторов",
        "btn_youtube": "▶️ Найти на YouTube",
        "offline_warning": (
            "⚠️ Нет интернета. Доступен только локальный ИИ-анализ и аудиоконвертер."
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 Нифига себе, вы наш фанат! Круто, что этот трек вышел у нас "
            "на Merphi Music Group!"
        ),
        "copy_button": "Копировать",
        "copied": "Скопировано!",
        "close_button": "Закрыть",
        "songdna_title": "Song DNA — Кредиты и анализ",
        "desc_title": "Описание для редакторов стриминговых сервисов",
        "youtube_views": "Просмотры YouTube",
        "youtube_channel": "Канал YouTube",
        "youtube_published": "Загружено",
        "spotify_found_acr": "Распознано через ACRCloud: {name}",
        "text_search_fallback": (
            "⚠️ Текстовый поиск: результаты могут быть неточны для нишевых/андеграунд треков."
        ),
        "songdna_section_credits": "Кредиты (YouTube)",
        "songdna_section_writers": "Авторы/Создатели (YouTube)",
        "youtube_distributor": "Дистрибьютор YouTube",
        "credits_note": "Примечание: глубокие кредиты (продюсеры/авторы) ограничены публичными стриминговыми API.",
        "spotify_open_btn": "Открыть в Spotify",
        "mood_positive": "Позитивное / Светлое",
        "mood_dark": "Тёмное / Меланхоличное",
        "spotify_source_local": "локальный анализ",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Audio Features в Spotify отключены — BPM/энергия/вайб из локального анализа.",
        "spotify_error": "Не удалось получить данные Spotify.",
        "spotify_rate_limited": "Достигнут лимит запросов Spotify — попробуйте позже (локальный анализ работает).",
        "na": "Н/Д",
        "unit_bit": "бит",
        "unit_channel": "канал",
        "unit_channels": "канала",
        "unknown": "Неизвестно",
        "msg_unsupported_title": "Неподдерживаемый файл",
        "msg_unsupported_body": "Выберите поддерживаемый аудиофайл:\n{extensions}",
        "msg_not_found_title": "Файл не найден",
        "msg_not_found_body": "Этот файл не удалось найти.",
        "msg_mediainfo_title": "Ошибка MediaInfo",
        "msg_mediainfo_body": "Не удалось прочитать метаданные файла.\n\n{error}\n\nУбедитесь, что MediaInfo установлен в системе.",
        "msg_no_file_title": "Файл не загружен",
        "msg_no_file_body": "Сначала загрузите аудиофайл для ИИ-анализа.",
        "file_dialog_title": "Выберите аудиофайл",
        "file_dialog_audio": "Аудиофайлы",
        "file_dialog_wav": "WAV файлы",
        "file_dialog_mp3": "MP3 файлы",
        "file_dialog_flac": "FLAC файлы",
        "file_dialog_all": "Все файлы",
        "audio_tools_header": "Аудио-инструменты",
        "convert_format_label": "Целевой формат",
        "convert_button": "Конвертировать и сохранить",
        "convert_success_title": "Конвертация завершена",
        "convert_success_body": "Сохранено в:\n{path}",
        "convert_error_title": "Ошибка конвертации",
        "convert_error_body": "Не удалось конвертировать файл.\n\n{error}",
        "convert_ffmpeg_error": (
            "Для конвертации нужен ffmpeg.\n\n"
            "Установите ffmpeg и добавьте в PATH, затем повторите.\n"
            "Скачать: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "Скачать обложку HD",
        "cover_saved_title": "Обложка сохранена",
        "cover_saved_body": "Сохранено в:\n{path}",
        "cover_no_url": "URL обложки для этого трека недоступен.",
        "cover_error_title": "Ошибка загрузки",
        "cover_error_body": "Не удалось скачать обложку.\n\n{error}",
        "songdna_section_release": "Релиз",
        "songdna_section_track": "Детали трека",
        "songdna_section_identifiers": "Идентификаторы",
        "songdna_section_analytics": "Аудио-аналитика",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "Трек",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "Слушать релиз",
        "pitch_editor_keys": "Ключи для редакторов",
        "card_file_title": "Файл и характеристики",
        "card_action_title": "Центр действий",
        "about_btn": "О нас",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Лейбл Merphi Music Group основан Артуром Мартемьяновым в 14 лет "
            "в поселке Кангалассы (г. Якутск)."
        ),
        "about_website_btn": "Сайт: merphimusic.com",
        "about_smartlink_btn": "Смартлинк: merphimusic.lnk.to/mmg",
        "about_btn": "О нас",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Лейбл Merphi Music Group основан Артуром Мартемьяновым в 14 лет "
            "в поселке Кангалассы (г. Якутск)."
        ),
        "about_website_btn": "Сайт: merphimusic.com",
        "about_smartlink_btn": "Смартлинк: merphimusic.lnk.to/mmg",
    },
    "ja": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "Merphi Music Group 提供",
        "drop_primary": "ここにオーディオファイルをドラッグ＆ドロップ",
        "drop_hint": "対応形式: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "ファイル未読み込み",
        "file_loaded_success": "ファイルを読み込みました",
        "browse_button": "ファイルを選択",
        "specs_header": "技術仕様",
        "spec_file_name": "ファイル名",
        "spec_format": "フォーマット",
        "spec_codec": "コーデック",
        "spec_bit_depth": "ビット深度",
        "spec_sampling_rate": "サンプリングレート",
        "spec_channels": "チャンネル",
        "spec_bitrate": "ビットレート",
        "spec_duration": "再生時間",
        "spec_daw_encoder": "DAW / エンコーダー",
        "analyze_button": "🔍 AIで分析",
        "ai_idle": "ファイルを読み込んでからAI分析を実行してください。",
        "ai_ready": "AI分析の準備ができました。",
        "ai_complete": "分析が完了しました。",
        "progress_scanning": "オーディオフィンガープリントをスキャン中...",
        "progress_spectral": "スペクトルパターンを分析中...",
        "progress_artifacts": "生成アーティファクトを確認中...",
        "progress_comparing": "モデルシグネチャと比較中...",
        "progress_finalizing": "信頼度スコアを確定中...",
        "ai_result": "AI生成の確率: {probability}% - {verdict}",
        "verdict_human": "人間",
        "verdict_ai": "AI",
        "progress_loading_model": "Deezer検出モデルを読み込み中...",
        "progress_running_model": "Deezer deepfake分析を実行中...",
        "msg_model_missing_title": "モデル未ダウンロード",
        "msg_model_missing_body": "Deezer PyTorch重みがありません。\n\nプロジェクトフォルダで実行:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "AI分析エラー",
        "msg_ai_error_body": "AI分析を完了できませんでした。\n\n{error}",
        "demo_button": "Merphi Music Group にデモを提出",
        "spotify_header": "Spotify インサイト",
        "spotify_idle": "ファイルを読み込んで Spotify で検索します。",
        "spotify_searching": "Spotify で検索中...",
        "spotify_found": "見つかりました: {name}",
        "spotify_not_found": "未リリースのデモ / 見つかりません",
        "spotify_label": "レーベル",
        "spotify_release": "リリース日",
        "spotify_mood": "ムード / バイブ",
        "spotify_bpm": "BPM / テンポ",
        "spotify_energy": "エネルギー",
        "spotify_danceability": "ダンス性",
        "spotify_popularity": "人気度",
        "spotify_key": "キー / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "ディストリビューター",
        "credits_artist": "アーティスト",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 編集者向け説明",
        "btn_youtube": "▶️ YouTube で検索",
        "offline_warning": (
            "⚠️ インターネット未接続。ローカルAI分析と変換のみ利用できます。"
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 すごい、真のファンですね！Merphi Music Group からリリースされた"
            "このトラック、最高です！"
        ),
        "copy_button": "コピー",
        "copied": "コピーしました！",
        "close_button": "閉じる",
        "songdna_title": "Song DNA — クレジットと分析",
        "desc_title": "ストリーミング編集者向けの説明",
        "youtube_views": "YouTube 再生回数",
        "youtube_channel": "YouTube チャンネル",
        "youtube_published": "アップロード",
        "spotify_found_acr": "ACRCloud で認識: {name}",
        "text_search_fallback": (
            "⚠️ テキスト検索フォールバック: ニッチ/アンダーグラウンド曲では結果が不正確な場合があります。"
        ),
        "songdna_section_credits": "クレジット (YouTube)",
        "songdna_section_writers": "作詞・作曲者 (YouTube)",
        "youtube_distributor": "YouTube ディストリビューター",
        "credits_note": "注: 深いクレジット（プロデューサー/作詞作曲）は公開ストリーミング API では制限されています。",
        "spotify_open_btn": "Spotify で開く",
        "mood_positive": "ポジティブ / 明るい",
        "mood_dark": "ダーク / メランコリック",
        "spotify_source_local": "ローカル分析",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Spotify の Audio Features は廃止されました — BPM/エネルギー/ムードはローカル分析です。",
        "spotify_error": "Spotify の取得に失敗しました。",
        "spotify_rate_limited": "Spotify のレート制限に達しました — 後でもう一度（ローカル分析は動作します）。",
        "na": "N/A",
        "unit_bit": "bit",
        "unit_channel": "チャンネル",
        "unit_channels": "チャンネル",
        "unknown": "不明",
        "msg_unsupported_title": "非対応ファイル",
        "msg_unsupported_body": "対応しているオーディオファイルを選択してください:\n{extensions}",
        "msg_not_found_title": "ファイルが見つかりません",
        "msg_not_found_body": "ファイルが見つかりませんでした。",
        "msg_mediainfo_title": "MediaInfoエラー",
        "msg_mediainfo_body": "ファイルのメタデータを読み取れませんでした。\n\n{error}\n\nMediaInfoがインストールされているか確認してください。",
        "msg_no_file_title": "ファイル未読み込み",
        "msg_no_file_body": "AI分析の前にオーディオファイルを読み込んでください。",
        "file_dialog_title": "オーディオファイルを選択",
        "file_dialog_audio": "オーディオファイル",
        "file_dialog_wav": "WAVファイル",
        "file_dialog_mp3": "MP3ファイル",
        "file_dialog_flac": "FLACファイル",
        "file_dialog_all": "すべてのファイル",
        "audio_tools_header": "オーディオツール",
        "convert_format_label": "出力形式",
        "convert_button": "変換して保存",
        "convert_success_title": "変換完了",
        "convert_success_body": "保存先:\n{path}",
        "convert_error_title": "変換エラー",
        "convert_error_body": "ファイルを変換できませんでした。\n\n{error}",
        "convert_ffmpeg_error": (
            "変換には ffmpeg が必要です。\n\n"
            "ffmpeg をインストールして PATH に追加してから再試行してください。\n"
            "ダウンロード: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "高解像度カバーをダウンロード",
        "cover_saved_title": "カバーを保存しました",
        "cover_saved_body": "保存先:\n{path}",
        "cover_no_url": "このトラックのカバー URL がありません。",
        "cover_error_title": "ダウンロード失敗",
        "cover_error_body": "カバーをダウンロードできませんでした。\n\n{error}",
        "songdna_section_release": "リリース",
        "songdna_section_track": "トラック詳細",
        "songdna_section_identifiers": "識別子",
        "songdna_section_analytics": "オーディオ分析",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "トラック",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "リリースを聴く",
        "pitch_editor_keys": "編集者向けキー",
        "card_file_title": "ファイルと技術仕様",
        "card_action_title": "アクションセンター",
        "about_btn": "私たちについて",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Merphi Music Group は、14 歳の時にヤクーツク・カンガラッシーで "
            "Artur Martemyanov によって設立されました。"
        ),
        "about_website_btn": "Website: merphimusic.com",
        "about_smartlink_btn": "Smartlink: merphimusic.lnk.to/mmg",
    },
    "zh": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "Merphi Music Group 出品",
        "drop_primary": "将音频文件拖放到此处",
        "drop_hint": "支持格式: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "未加载文件",
        "file_loaded_success": "文件加载成功",
        "browse_button": "浏览文件",
        "specs_header": "技术规格",
        "spec_file_name": "文件名",
        "spec_format": "格式",
        "spec_codec": "编解码器",
        "spec_bit_depth": "位深度",
        "spec_sampling_rate": "采样率",
        "spec_channels": "声道",
        "spec_bitrate": "比特率",
        "spec_duration": "时长",
        "spec_daw_encoder": "DAW / 编码器",
        "analyze_button": "🔍 AI 分析",
        "ai_idle": "请先加载文件，然后运行 AI 分析。",
        "ai_ready": "已准备好进行 AI 分析。",
        "ai_complete": "分析完成。",
        "progress_scanning": "正在扫描音频指纹...",
        "progress_spectral": "正在分析频谱模式...",
        "progress_artifacts": "正在检查生成伪影...",
        "progress_comparing": "正在比对模型特征...",
        "progress_finalizing": "正在计算置信度...",
        "ai_result": "AI 生成概率: {probability}% - {verdict}",
        "verdict_human": "人类",
        "verdict_ai": "AI",
        "progress_loading_model": "正在加载 Deezer 检测模型...",
        "progress_running_model": "正在运行 Deezer deepfake 分析...",
        "msg_model_missing_title": "模型未下载",
        "msg_model_missing_body": "缺少 Deezer PyTorch 权重。\n\n在项目文件夹中运行:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "AI 分析失败",
        "msg_ai_error_body": "无法完成 AI 分析。\n\n{error}",
        "demo_button": "向 Merphi Music Group 提交 Demo",
        "spotify_header": "Spotify 洞察",
        "spotify_idle": "加载文件以在 Spotify 中搜索。",
        "spotify_searching": "正在 Spotify 搜索...",
        "spotify_found": "已找到: {name}",
        "spotify_not_found": "未发行 Demo / 未找到",
        "spotify_label": "唱片公司",
        "spotify_release": "发行日期",
        "spotify_mood": "情绪 / 氛围",
        "spotify_bpm": "BPM / 速度",
        "spotify_energy": "能量",
        "spotify_danceability": "可舞性",
        "spotify_popularity": "热度",
        "spotify_key": "调性 / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "发行商",
        "credits_artist": "艺人",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 编辑描述",
        "btn_youtube": "▶️ 在 YouTube 搜索",
        "offline_warning": (
            "⚠️ 无网络连接。仅可使用本地 AI 分析和音频转换器。"
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 哇，你是我们的铁杆粉丝！很高兴这首曲目在 Merphi Music Group 发行！"
        ),
        "copy_button": "复制",
        "copied": "已复制！",
        "close_button": "关闭",
        "songdna_title": "Song DNA — 制作信息与分析",
        "desc_title": "面向流媒体编辑的描述",
        "youtube_views": "YouTube 播放量",
        "youtube_channel": "YouTube 频道",
        "youtube_published": "上传于",
        "spotify_found_acr": "通过 ACRCloud 识别: {name}",
        "text_search_fallback": (
            "⚠️ 文本搜索回退: 对于小众/地下曲目，结果可能不准确。"
        ),
        "songdna_section_credits": "制作信息 (YouTube)",
        "songdna_section_writers": "词曲作者 (YouTube)",
        "youtube_distributor": "YouTube 发行商",
        "credits_note": "注意：深层制作信息（制作人/词曲作者）受公开流媒体 API 限制。",
        "spotify_open_btn": "在 Spotify 中打开",
        "mood_positive": "积极 / 明亮",
        "mood_dark": "黑暗 / 忧郁",
        "spotify_source_local": "本地分析",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Spotify 音频特征已弃用 — BPM/能量/情绪来自本地分析。",
        "spotify_error": "Spotify 查询失败。",
        "spotify_rate_limited": "已达到 Spotify 速率限制 — 请稍后重试（本地分析仍可用）。",
        "na": "N/A",
        "unit_bit": "位",
        "unit_channel": "声道",
        "unit_channels": "声道",
        "unknown": "未知",
        "msg_unsupported_title": "不支持的文件",
        "msg_unsupported_body": "请选择支持的音频文件:\n{extensions}",
        "msg_not_found_title": "未找到文件",
        "msg_not_found_body": "无法找到该文件。",
        "msg_mediainfo_title": "MediaInfo 错误",
        "msg_mediainfo_body": "无法读取文件元数据。\n\n{error}\n\n请确保系统已安装 MediaInfo。",
        "msg_no_file_title": "未加载文件",
        "msg_no_file_body": "请先加载音频文件再进行 AI 分析。",
        "file_dialog_title": "选择音频文件",
        "file_dialog_audio": "音频文件",
        "file_dialog_wav": "WAV 文件",
        "file_dialog_mp3": "MP3 文件",
        "file_dialog_flac": "FLAC 文件",
        "file_dialog_all": "所有文件",
        "audio_tools_header": "音频工具",
        "convert_format_label": "目标格式",
        "convert_button": "转换并保存",
        "convert_success_title": "转换完成",
        "convert_success_body": "已保存至:\n{path}",
        "convert_error_title": "转换失败",
        "convert_error_body": "无法转换文件。\n\n{error}",
        "convert_ffmpeg_error": (
            "音频转换需要 ffmpeg。\n\n"
            "请安装 ffmpeg 并添加到 PATH 后重试。\n"
            "下载: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "下载高清封面",
        "cover_saved_title": "封面已保存",
        "cover_saved_body": "已保存至:\n{path}",
        "cover_no_url": "此曲目没有可用的封面 URL。",
        "cover_error_title": "下载失败",
        "cover_error_body": "无法下载封面。\n\n{error}",
        "songdna_section_release": "发行信息",
        "songdna_section_track": "曲目详情",
        "songdna_section_identifiers": "标识符",
        "songdna_section_analytics": "音频分析",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "曲目",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "收听发行",
        "pitch_editor_keys": "编辑关键信息",
        "card_file_title": "文件与技术规格",
        "card_action_title": "操作中心",
        "about_btn": "关于我们",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Merphi Music Group 由 Artur Martemyanov 在 14 岁时于 Kangalassy（雅库茨克）创立。"
        ),
        "about_website_btn": "网站: merphimusic.com",
        "about_smartlink_btn": "Smartlink: merphimusic.lnk.to/mmg",
    },
    "pt": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "Um produto da Merphi Music Group",
        "drop_primary": "Arraste e solte um arquivo de áudio aqui",
        "drop_hint": "Formatos suportados: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "Nenhum arquivo carregado",
        "file_loaded_success": "Arquivo carregado com sucesso",
        "browse_button": "Procurar arquivo",
        "specs_header": "Especificações Técnicas",
        "spec_file_name": "Nome do arquivo",
        "spec_format": "Formato",
        "spec_codec": "Codec",
        "spec_bit_depth": "Profundidade de bits",
        "spec_sampling_rate": "Taxa de amostragem",
        "spec_channels": "Canais",
        "spec_bitrate": "Bitrate",
        "spec_duration": "Duração",
        "spec_daw_encoder": "DAW / Codificador",
        "analyze_button": "🔍 Analisar com IA",
        "ai_idle": "Carregue um arquivo e execute a análise com IA.",
        "ai_ready": "Pronto para análise com IA.",
        "ai_complete": "Análise concluída.",
        "progress_scanning": "Escaneando impressão digital do áudio...",
        "progress_spectral": "Analisando padrões espectrais...",
        "progress_artifacts": "Verificando artefatos generativos...",
        "progress_comparing": "Comparando com assinaturas de modelos...",
        "progress_finalizing": "Finalizando pontuação de confiança...",
        "ai_result": "Probabilidade de geração por IA: {probability}% - {verdict}",
        "verdict_human": "Humano",
        "verdict_ai": "IA",
        "progress_loading_model": "Carregando modelo Deezer...",
        "progress_running_model": "Executando análise Deezer deepfake...",
        "msg_model_missing_title": "Modelo não baixado",
        "msg_model_missing_body": "Pesos PyTorch do Deezer ausentes.\n\nExecute na pasta do projeto:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "Falha na análise com IA",
        "msg_ai_error_body": "Não foi possível concluir a análise com IA.\n\n{error}",
        "demo_button": "Enviar Demo para Merphi Music Group",
        "spotify_header": "Spotify Insights",
        "spotify_idle": "Carregue um arquivo para buscar no Spotify.",
        "spotify_searching": "Buscando no Spotify...",
        "spotify_found": "Encontrado: {name}",
        "spotify_not_found": "Demo Não Lançada / Não Encontrada",
        "spotify_label": "Gravadora",
        "spotify_release": "Data de Lançamento",
        "spotify_mood": "Humor / Vibe",
        "spotify_bpm": "BPM / Andamento",
        "spotify_energy": "Energia",
        "spotify_danceability": "Dançabilidade",
        "spotify_popularity": "Popularidade",
        "spotify_key": "Tom / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "Distribuidora",
        "credits_artist": "Artista",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 Descrição editorial",
        "btn_youtube": "▶️ Buscar no YouTube",
        "offline_warning": (
            "⚠️ Sem internet. Apenas análise local de IA e conversor de áudio disponíveis."
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 Uau, você é fã de verdade! Incrível que esta faixa saiu pela "
            "Merphi Music Group!"
        ),
        "copy_button": "Copiar",
        "copied": "Copiado!",
        "close_button": "Fechar",
        "songdna_title": "Song DNA — Créditos e análise",
        "desc_title": "Descrição editorial para editores de streaming",
        "youtube_views": "Visualizações no YouTube",
        "youtube_channel": "Canal do YouTube",
        "youtube_published": "Publicado",
        "spotify_found_acr": "Reconhecido via ACRCloud: {name}",
        "text_search_fallback": (
            "⚠️ Busca por texto: resultados podem ser imprecisos para faixas de nicho/underground."
        ),
        "songdna_section_credits": "Créditos (YouTube)",
        "songdna_section_writers": "Autores/Criadores (YouTube)",
        "youtube_distributor": "Distribuidor YouTube",
        "credits_note": "Nota: créditos profundos (produtores/compositores) são restritos pelas APIs públicas de streaming.",
        "spotify_open_btn": "Abrir no Spotify",
        "mood_positive": "Positivo / Brilhante",
        "mood_dark": "Sombrio / Melancólico",
        "spotify_source_local": "análise local",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Os audio features do Spotify foram descontinuados — BPM/Energia/Humor de análise local.",
        "spotify_error": "Falha na consulta ao Spotify.",
        "spotify_rate_limited": "Limite de requisições do Spotify atingido — tente mais tarde (a análise local funciona).",
        "na": "N/D",
        "unit_bit": "bit",
        "unit_channel": "canal",
        "unit_channels": "canais",
        "unknown": "Desconhecido",
        "msg_unsupported_title": "Arquivo não suportado",
        "msg_unsupported_body": "Escolha um arquivo de áudio suportado:\n{extensions}",
        "msg_not_found_title": "Arquivo não encontrado",
        "msg_not_found_body": "Não foi possível encontrar esse arquivo.",
        "msg_mediainfo_title": "Erro do MediaInfo",
        "msg_mediainfo_body": "Não foi possível ler os metadados do arquivo.\n\n{error}\n\nCertifique-se de que o MediaInfo está instalado.",
        "msg_no_file_title": "Nenhum arquivo carregado",
        "msg_no_file_body": "Carregue um arquivo de áudio antes da análise com IA.",
        "file_dialog_title": "Selecionar arquivo de áudio",
        "file_dialog_audio": "Arquivos de áudio",
        "file_dialog_wav": "Arquivos WAV",
        "file_dialog_mp3": "Arquivos MP3",
        "file_dialog_flac": "Arquivos FLAC",
        "file_dialog_all": "Todos os arquivos",
        "audio_tools_header": "Ferramentas de Áudio",
        "convert_format_label": "Formato de destino",
        "convert_button": "Converter e Salvar",
        "convert_success_title": "Conversão concluída",
        "convert_success_body": "Salvo em:\n{path}",
        "convert_error_title": "Falha na conversão",
        "convert_error_body": "Não foi possível converter o arquivo.\n\n{error}",
        "convert_ffmpeg_error": (
            "ffmpeg é necessário para conversão de áudio.\n\n"
            "Instale o ffmpeg e adicione ao PATH, depois tente novamente.\n"
            "Download: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "Baixar capa em alta resolução",
        "cover_saved_title": "Capa salva",
        "cover_saved_body": "Salva em:\n{path}",
        "cover_no_url": "Nenhuma URL de capa disponível para esta faixa.",
        "cover_error_title": "Falha no download",
        "cover_error_body": "Não foi possível baixar a capa.\n\n{error}",
        "songdna_section_release": "Lançamento",
        "songdna_section_track": "Detalhes da faixa",
        "songdna_section_identifiers": "Identificadores",
        "songdna_section_analytics": "Análise de áudio",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "Faixa",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "Ouvir o lançamento",
        "pitch_editor_keys": "Chaves para editores",
        "card_file_title": "Arquivo e especificações",
        "card_action_title": "Centro de ações",
        "about_btn": "Sobre nós",
        "about_title": "Merphi Music Group",
        "about_body": (
            "A Merphi Music Group foi fundada por Artur Martemyanov aos 14 anos "
            "em Kangalassy (Yakutsk)."
        ),
        "about_website_btn": "Site: merphimusic.com",
        "about_smartlink_btn": "Smartlink: merphimusic.lnk.to/mmg",
    },
    "es": {
        "app_title": "Merphi Audio Inspector",
        "subtitle": "Un producto de Merphi Music Group",
        "drop_primary": "Arrastra y suelta un archivo de audio aquí",
        "drop_hint": "Formatos compatibles: .wav  ·  .mp3  ·  .flac",
        "no_file_loaded": "Ningún archivo cargado",
        "file_loaded_success": "Archivo cargado correctamente",
        "browse_button": "Buscar archivo",
        "specs_header": "Especificaciones Técnicas",
        "spec_file_name": "Nombre del archivo",
        "spec_format": "Formato",
        "spec_codec": "Códec",
        "spec_bit_depth": "Profundidad de bits",
        "spec_sampling_rate": "Frecuencia de muestreo",
        "spec_channels": "Canales",
        "spec_bitrate": "Bitrate",
        "spec_duration": "Duración",
        "spec_daw_encoder": "DAW / Codificador",
        "analyze_button": "🔍 Analizar con IA",
        "ai_idle": "Carga un archivo y luego ejecuta el análisis con IA.",
        "ai_ready": "Listo para análisis con IA.",
        "ai_complete": "Análisis completado.",
        "progress_scanning": "Escaneando huella de audio...",
        "progress_spectral": "Analizando patrones espectrales...",
        "progress_artifacts": "Comprobando artefactos generativos...",
        "progress_comparing": "Comparando con firmas de modelos...",
        "progress_finalizing": "Finalizando puntuación de confianza...",
        "ai_result": "Probabilidad de generación por IA: {probability}% - {verdict}",
        "verdict_human": "Humano",
        "verdict_ai": "IA",
        "progress_loading_model": "Cargando modelo Deezer...",
        "progress_running_model": "Ejecutando análisis Deezer deepfake...",
        "msg_model_missing_title": "Modelo no descargado",
        "msg_model_missing_body": "Faltan los pesos PyTorch de Deezer.\n\nEjecute en la carpeta del proyecto:\n1) python download_model.py\n2) python convert_tf_to_torch.py",
        "msg_ai_error_title": "Error de análisis con IA",
        "msg_ai_error_body": "No se pudo completar el análisis con IA.\n\n{error}",
        "demo_button": "Enviar Demo a Merphi Music Group",
        "spotify_header": "Spotify Insights",
        "spotify_idle": "Carga un archivo para buscarlo en Spotify.",
        "spotify_searching": "Buscando en Spotify...",
        "spotify_found": "Encontrado: {name}",
        "spotify_not_found": "Demo No Publicada / No Encontrada",
        "spotify_label": "Sello discográfico",
        "spotify_release": "Fecha de lanzamiento",
        "spotify_mood": "Estado de ánimo / Vibe",
        "spotify_bpm": "BPM / Tempo",
        "spotify_energy": "Energía",
        "spotify_danceability": "Bailabilidad",
        "spotify_popularity": "Popularidad",
        "spotify_key": "Tonalidad / Camelot",
        "spotify_isrc": "ISRC",
        "spotify_upc": "UPC",
        "spotify_distributor": "Distribuidora",
        "credits_artist": "Artista",
        "btn_songdna": "🎵 Song DNA",
        "btn_description": "📝 Descripción editorial",
        "btn_youtube": "▶️ Buscar en YouTube",
        "offline_warning": (
            "⚠️ Sin internet. Solo análisis local de IA y convertidor de audio disponibles."
        ),
        "easter_egg_title": "Merphi Music Group",
        "easter_egg_message": (
            "🎉 ¡Increíble, eres un fan de verdad! Genial que este tema salió en "
            "Merphi Music Group!"
        ),
        "copy_button": "Copiar",
        "copied": "¡Copiado!",
        "close_button": "Cerrar",
        "songdna_title": "Song DNA — Créditos y análisis",
        "desc_title": "Descripción editorial para editores de streaming",
        "youtube_views": "Reproducciones de YouTube",
        "youtube_channel": "Canal de YouTube",
        "youtube_published": "Publicado",
        "spotify_found_acr": "Reconocido vía ACRCloud: {name}",
        "text_search_fallback": (
            "⚠️ Búsqueda por texto: los resultados pueden ser imprecisos para pistas de nicho/underground."
        ),
        "songdna_section_credits": "Créditos (YouTube)",
        "songdna_section_writers": "Autores/Creadores (YouTube)",
        "youtube_distributor": "Distribuidor YouTube",
        "credits_note": "Nota: los créditos profundos (productores/compositores) están restringidos por las APIs públicas de streaming.",
        "spotify_open_btn": "Abrir en Spotify",
        "mood_positive": "Positivo / Brillante",
        "mood_dark": "Oscuro / Melancólico",
        "spotify_source_local": "análisis local",
        "spotify_source_spotify": "Spotify",
        "spotify_note_local": "Las audio features de Spotify están obsoletas — BPM/Energía/Ánimo de análisis local.",
        "spotify_error": "Error al consultar Spotify.",
        "spotify_rate_limited": "Se alcanzó el límite de Spotify — inténtalo más tarde (el análisis local funciona).",
        "na": "N/D",
        "unit_bit": "bit",
        "unit_channel": "canal",
        "unit_channels": "canales",
        "unknown": "Desconocido",
        "msg_unsupported_title": "Archivo no compatible",
        "msg_unsupported_body": "Elige un archivo de audio compatible:\n{extensions}",
        "msg_not_found_title": "Archivo no encontrado",
        "msg_not_found_body": "No se pudo encontrar ese archivo.",
        "msg_mediainfo_title": "Error de MediaInfo",
        "msg_mediainfo_body": "No se pudieron leer los metadatos del archivo.\n\n{error}\n\nAsegúrate de que MediaInfo esté instalado.",
        "msg_no_file_title": "Ningún archivo cargado",
        "msg_no_file_body": "Carga un archivo de audio antes del análisis con IA.",
        "file_dialog_title": "Seleccionar archivo de audio",
        "file_dialog_audio": "Archivos de audio",
        "file_dialog_wav": "Archivos WAV",
        "file_dialog_mp3": "Archivos MP3",
        "file_dialog_flac": "Archivos FLAC",
        "file_dialog_all": "Todos los archivos",
        "audio_tools_header": "Herramientas de Audio",
        "convert_format_label": "Formato de destino",
        "convert_button": "Convertir y Guardar",
        "convert_success_title": "Conversión completada",
        "convert_success_body": "Guardado en:\n{path}",
        "convert_error_title": "Error de conversión",
        "convert_error_body": "No se pudo convertir el archivo.\n\n{error}",
        "convert_ffmpeg_error": (
            "Se requiere ffmpeg para la conversión de audio.\n\n"
            "Instala ffmpeg y añádelo al PATH, luego inténtalo de nuevo.\n"
            "Descarga: https://ffmpeg.org/download.html"
        ),
        "btn_download_cover": "Descargar portada HD",
        "cover_saved_title": "Portada guardada",
        "cover_saved_body": "Guardada en:\n{path}",
        "cover_no_url": "No hay URL de portada disponible para esta pista.",
        "cover_error_title": "Error de descarga",
        "cover_error_body": "No se pudo descargar la portada.\n\n{error}",
        "songdna_section_release": "Lanzamiento",
        "songdna_section_track": "Detalles de la pista",
        "songdna_section_identifiers": "Identificadores",
        "songdna_section_analytics": "Análisis de audio",
        "songdna_section_youtube": "YouTube",
        "songdna_track_name": "Pista",
        "pitch_genre_electronic": "Electronic / Dance",
        "pitch_genre_pop": "Pop / Mainstream",
        "pitch_genre_hiphop": "Hip-Hop / Trap",
        "pitch_genre_chill": "Lo-Fi / Chill",
        "pitch_genre_general": "Cross-genre / Discovery",
        "pitch_listen_link": "Escuchar el lanzamiento",
        "pitch_editor_keys": "Claves para editores",
        "card_file_title": "Archivo y especificaciones",
        "card_action_title": "Centro de acciones",
        "about_btn": "Sobre nosotros",
        "about_title": "Merphi Music Group",
        "about_body": (
            "Merphi Music Group fue fundado por Artur Martemyanov a los 14 años "
            "en Kangalassy (Yakutsk)."
        ),
        "about_website_btn": "Sitio: merphimusic.com",
        "about_smartlink_btn": "Smartlink: merphimusic.lnk.to/mmg",
    },
}


# ---------------------------------------------------------------------------
# Editorial description generator (offline, multilingual)
# ---------------------------------------------------------------------------

PITCH_TEMPLATES = {
    "en": {
        "headline": "🔥 Meet the new release: {artist} — {title}!",
        "body": (
            "This track carries a deep {mood} vibe with a pulsing rhythm ({bpm} BPM) — "
            "a perfect fit for curated and editorial playlists.\n"
            "Sound profile: Energy {energy}%, Danceability {dance}%.\n"
            "Listeners will find a dense, immersive sound that holds attention from the first seconds."
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | Genre: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "Positive / Bright",
        "mood_neg": "Dark / Melancholic",
    },
    "ru": {
        "headline": "🔥 Встречайте новый релиз: {artist} — {title}!",
        "body": (
            "Этот трек с глубоким {mood} вайбом и пульсирующим ритмом ({bpm} BPM) "
            "идеально впишется в кураторские и редакционные плейлисты.\n"
            "Особенности звучания: Энергия {energy}%, Танцевальность {dance}%.\n"
            "Слушатели найдут здесь плотный звук и атмосферу, которая удерживает внимание с первых секунд."
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | Жанр: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "позитивным",
        "mood_neg": "меланхоличным",
    },
    "ja": {
        "headline": "🔥 新リリース: {artist} — {title}!",
        "body": (
            "深い{mood}な雰囲気と脈打つリズム（{bpm} BPM）のこのトラックは、"
            "キュレーションおよびエディトリアルプレイリストに最適です。\n"
            "サウンド特性: エネルギー {energy}%、ダンス性 {dance}%。\n"
            "最初の数秒から聴き手の注意を引く、密度の高いサウンドです。"
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | ジャンル: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "明るく前向きな",
        "mood_neg": "ダークでメランコリックな",
    },
    "zh": {
        "headline": "🔥 全新发行: {artist} — {title}!",
        "body": (
            "这首曲目拥有深沉的{mood}氛围与脉动节奏（{bpm} BPM），"
            "非常适合策展与编辑类歌单。\n"
            "声音特征: 能量 {energy}%，可舞性 {dance}%。\n"
            "听众将从第一秒起被其密集、沉浸的声音所吸引。"
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | 风格: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "明亮积极",
        "mood_neg": "黑暗忧郁",
    },
    "pt": {
        "headline": "🔥 Conheça o novo lançamento: {artist} — {title}!",
        "body": (
            "Esta faixa traz um vibe {mood} profundo com ritmo pulsante ({bpm} BPM) — "
            "ideal para playlists curadas e editoriais.\n"
            "Perfil sonoro: Energia {energy}%, Dançabilidade {dance}%.\n"
            "O ouvinte encontrará um som denso e envolvente desde os primeiros segundos."
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | Gênero: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "positivo e brilhante",
        "mood_neg": "sombrio e melancólico",
    },
    "es": {
        "headline": "🔥 Conoce el nuevo lanzamiento: {artist} — {title}!",
        "body": (
            "Esta pista tiene un vibe {mood} profundo y un ritmo pulsante ({bpm} BPM) — "
            "ideal para playlists curadas y editoriales.\n"
            "Perfil sonoro: Energía {energy}%, Bailabilidad {dance}%.\n"
            "Los oyentes encontrarán un sonido denso e inmersivo desde los primeros segundos."
        ),
        "keys": "{editor_keys}: ISRC: {isrc} | Género: {genre}",
        "link": "{listen}: {link}",
        "mood_pos": "positivo y brillante",
        "mood_neg": "oscuro y melancólico",
    },
}


def _guess_genre_key(d: dict) -> str:
    energy = float(d.get("energy") or 0.0)
    dance = float(d.get("dance") or 0.0)
    bpm = float(d.get("bpm") or 120)
    if dance >= 0.68 and energy >= 0.62 and bpm >= 118:
        return "pitch_genre_electronic"
    if dance >= 0.55 and energy >= 0.45 and bpm >= 95:
        return "pitch_genre_pop"
    if bpm >= 130 and energy >= 0.55:
        return "pitch_genre_hiphop"
    if energy < 0.42:
        return "pitch_genre_chill"
    return "pitch_genre_general"


def _split_artist_title(name: str) -> tuple[str, str]:
    if not name:
        return "—", "—"
    for sep in (" — ", " - ", " – "):
        if sep in name:
            parts = name.split(sep, 1)
            return parts[0].strip() or "—", parts[1].strip() or "—"
    return "—", name.strip() or "—"


def generate_track_description(lang: str, d: dict, t_func=None) -> str:
    """Build a marketing pitch for streaming editors."""
    tpl = PITCH_TEMPLATES.get(lang, PITCH_TEMPLATES["en"])
    artist, title = _split_artist_title(d.get("title") or "")
    if artist == "—" and d.get("artist"):
        artist = d["artist"]
    if title == "—" and d.get("track_title"):
        title = d["track_title"]

    bpm = d.get("bpm") or "—"
    energy_f = float(d.get("energy") or 0.0)
    dance_f = float(d.get("dance") or 0.0)
    mood = tpl["mood_pos"] if d.get("mood_positive") else tpl["mood_neg"]
    isrc = d.get("isrc") or "—"
    link = d.get("link") or "—"

    if t_func:
        genre = t_func(_guess_genre_key(d))
        editor_keys = t_func("pitch_editor_keys")
        listen = t_func("pitch_listen_link")
    else:
        genre = _guess_genre_key(d)
        editor_keys = "Keys for editors"
        listen = "Listen to the release"

    headline = tpl["headline"].format(artist=artist, title=title)
    body = tpl["body"].format(
        mood=mood, bpm=bpm,
        energy=round(energy_f * 100), dance=round(dance_f * 100),
    )
    keys = tpl["keys"].format(editor_keys=editor_keys, isrc=isrc, genre=genre)
    link_line = tpl["link"].format(listen=listen, link=link)
    return f"{headline}\n{body}\n{keys}\n{link_line}"


def configure_pydub_ffmpeg() -> str | None:
    """Return path to ffmpeg.exe in the project root if the file exists."""
    if os.path.isfile(ffmpeg_path):
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path
        return ffmpeg_path
    return None


def _parse_version(version: str) -> tuple[int, ...]:
    cleaned = re.sub(r"^v", "", (version or "").strip(), flags=re.IGNORECASE)
    parts: list[int] = []
    for chunk in re.split(r"[.\-+]", cleaned):
        if chunk.isdigit():
            parts.append(int(chunk))
    return tuple(parts) if parts else (0,)


def _is_newer_version(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def check_for_updates(app: "MerphiAudioInspector") -> None:
    """Background update check against a remote version manifest."""
    if not check_internet_connection():
        return
    try:
        req = urllib.request.Request(
            UPDATE_CHECK_URL,
            headers={"User-Agent": f"MerphiAudioInspector/{APP_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return

    remote_version = str(
        payload.get("version") or payload.get("app_version") or ""
    ).strip()
    download_url = str(
        payload.get("download_url") or payload.get("url") or ""
    ).strip()
    if not remote_version or not _is_newer_version(remote_version, APP_VERSION):
        return

    message = (
        f"Доступна новая версия (v{remote_version}). "
        "Хотите скачать обновление?"
    )

    def _prompt() -> None:
        if CTKMESSAGEBOX_AVAILABLE:
            box = CTkMessagebox(
                title="Merphi Audio Inspector",
                message=message,
                icon="info",
                option_1="Скачать",
                option_2="Позже",
            )
            if box.get() == "Скачать" and download_url:
                webbrowser.open(download_url)
            return
        if messagebox.askyesno("Merphi Audio Inspector", message) and download_url:
            webbrowser.open(download_url)

    app.after(0, _prompt)


def _apply_window_icon(window: tk.Misc) -> None:
    if os.path.isfile(icon_path):
        try:
            window.iconbitmap(icon_path)
        except tk.TclError:
            pass


def check_internet_connection(timeout: float = 3.0) -> bool:
    """Return True if a reliable outbound connection appears available."""
    for host, port in (("8.8.8.8", 53), ("1.1.1.1", 53)):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    try:
        socket.gethostbyname("google.com")
        return True
    except OSError:
        return False


def resolve_initial_language() -> str:
    """Read installer-written config.ini and map to an app language code."""
    default = LANGUAGE_OPTIONS[DEFAULT_LANGUAGE_LABEL]
    if not CONFIG_PATH.is_file():
        return default
    try:
        parser = configparser.ConfigParser()
        parser.read(CONFIG_PATH, encoding="utf-8")
        raw = parser.get("Merphi", "Language", fallback="").strip().lower()
        code = INSTALLER_LANG_MAP.get(raw)
        if code and code in TRANSLATIONS:
            return code
    except Exception:
        pass
    return default


def language_label_for_code(code: str) -> str:
    for label, lang_code in LANGUAGE_OPTIONS.items():
        if lang_code == code:
            return label
    return DEFAULT_LANGUAGE_LABEL


def _is_mmg_label(label: str | None) -> bool:
    return bool(label and MMG_LABEL_MARKER in label.lower())


def _load_logo_image() -> ctk.CTkImage | None:
    if not PIL_AVAILABLE or not os.path.isfile(icon_path):
        return None
    try:
        pil_img = Image.open(icon_path)
        return ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(LOGO_DISPLAY_SIZE, LOGO_DISPLAY_SIZE),
        )
    except Exception:
        return None


class MerphiAudioInspector(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.font_family = (
            "Montserrat" if "Montserrat" in set(tkfont.families()) else "Segoe UI"
        )
        self.current_lang = resolve_initial_language()
        self._glass_enabled = False
        self._offline_mode = not check_internet_connection()
        self._mmg_easter_egg_shown_for: str | None = None
        self._logo_image = _load_logo_image()
        self.current_file: str | None = None
        self.current_specs: dict[str, str] = {}
        self.is_analyzing = False
        self.file_loaded = False
        self.ai_state = "idle"
        self.last_ai_probability: float | None = None
        self._pulse_active = False
        self._pulse_direction = 1
        self._pulse_value = 0.05
        self._pulse_job: str | None = None
        self.spotify_result: dict | None = None
        self.spotify_url: str | None = None
        self.spotify_token = 0
        self._cover_image = None
        self.youtube_result: dict | None = None
        self.youtube_url: str | None = None
        self.youtube_pending = False

        self.title(self._t("app_title"))
        self.geometry(WINDOW_SIZE)
        self.minsize(820, 720)
        _apply_window_icon(self)

        configure_pydub_ffmpeg()
        self._build_ui()
        self._setup_drag_and_drop()
        self._apply_language()
        self._update_offline_banner()
        self.update_idletasks()
        self.after(150, self._apply_glass_style)
        if check_internet_connection():
            self.after(800, lambda: threading.Thread(
                target=check_for_updates, args=(self,), daemon=True
            ).start())

    def _apply_glass_style(self) -> None:
        if not PYWINSTYLES_AVAILABLE:
            return
        for style in ("mica", "acrylic"):
            try:
                pywinstyles.apply_style(self, style)
                self._glass_enabled = True
                return
            except Exception:
                continue

    def _update_offline_banner(self) -> None:
        if self._offline_mode:
            self.offline_banner.configure(text=self._t("offline_warning"))
            self.offline_banner.grid()
        else:
            self.offline_banner.grid_remove()

    def _set_offline_mode(self, offline: bool) -> None:
        self._offline_mode = offline
        self._update_offline_banner()

    def _show_mmg_easter_egg(self) -> None:
        if CTKMESSAGEBOX_AVAILABLE:
            CTkMessagebox(
                title=self._t("easter_egg_title"),
                message=self._t("easter_egg_message"),
                icon="check",
                option_1="OK",
            )
            return
        messagebox.showinfo(
            self._t("easter_egg_title"),
            self._t("easter_egg_message"),
        )

    def _maybe_trigger_mmg_easter_egg(self, result: dict) -> None:
        label = result.get("label")
        if not _is_mmg_label(label):
            return
        track_key = result.get("matched_name") or label or ""
        if self._mmg_easter_egg_shown_for == track_key:
            return
        self._mmg_easter_egg_shown_for = track_key
        self.after(400, self._show_mmg_easter_egg)

    def _t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS[self.current_lang].get(key, TRANSLATIONS["en"][key])
        return text.format(**kwargs) if kwargs else text

    def _font(self, size: int = 13, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()

        self.offline_banner = ctk.CTkLabel(
            self,
            text="",
            font=self._font(size=12, weight="bold"),
            text_color=COLOR_WARNING,
            fg_color="#FFF7ED",
            corner_radius=10,
            anchor="w",
            wraplength=860,
            justify="left",
        )
        self.offline_banner.grid(
            row=1, column=0, sticky="ew", padx=28, pady=(0, 6)
        )
        self.offline_banner.grid_remove()

        self.main_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLOR_SURFACE_ALT,
            scrollbar_button_hover_color=COLOR_BORDER,
        )
        self.main_scroll.grid(row=2, column=0, sticky="nsew")
        self.main_scroll.grid_columnconfigure(0, weight=1)

        wrapper = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        wrapper.grid(row=0, column=0, sticky="ew", pady=(12, 28))
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_columnconfigure(1, weight=0)
        wrapper.grid_columnconfigure(2, weight=1)

        content = ctk.CTkFrame(wrapper, fg_color="transparent", width=MAX_CONTENT_WIDTH)
        content.grid(row=0, column=1, sticky="n")
        content.grid_columnconfigure(0, weight=1)

        self._build_card_file(content)
        self._build_card_analytics(content)
        self._build_card_actions(content)

    def _card(self, parent, row: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            corner_radius=18,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.grid(
            row=row, column=0, sticky="ew",
            padx=4, pady=(0, PANEL_GAP),
        )
        card.grid_columnconfigure(0, weight=1)
        return card

    def _card_title(self, parent, row: int, attr: str) -> None:
        lbl = ctk.CTkLabel(
            parent,
            text="",
            font=self._font(size=15, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        )
        lbl.grid(row=row, column=0, sticky="w", padx=22, pady=(18, 10))
        setattr(self, attr, lbl)

    def _build_card_file(self, parent) -> None:
        card = self._card(parent, 0)

        self._card_title(card, 0, "card_file_title_lbl")

        drop_row = ctk.CTkFrame(card, fg_color="transparent")
        drop_row.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
        drop_row.grid_columnconfigure(0, weight=1)

        self.drop_zone = ctk.CTkFrame(
            drop_row,
            fg_color=COLOR_CARD_INNER,
            border_width=2,
            border_color=COLOR_BORDER,
            corner_radius=14,
            height=118,
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew")
        self.drop_zone.grid_propagate(False)
        self.drop_zone.grid_columnconfigure(0, weight=1)

        self.drop_icon = ctk.CTkLabel(
            self.drop_zone, text="♪",
            font=self._font(size=30), text_color=COLOR_ACCENT,
        )
        self.drop_icon.grid(row=0, column=0, pady=(16, 0))

        self.drop_label = ctk.CTkLabel(
            self.drop_zone, text="",
            font=self._font(size=15, weight="bold"), text_color=COLOR_TEXT,
        )
        self.drop_label.grid(row=1, column=0, pady=(4, 0))

        self.drop_hint = ctk.CTkLabel(
            self.drop_zone, text="",
            font=self._font(size=11), text_color=COLOR_MUTED,
        )
        self.drop_hint.grid(row=2, column=0, pady=(2, 0))

        self.file_label = ctk.CTkLabel(
            self.drop_zone, text="",
            font=self._font(size=10), text_color=COLOR_MUTED,
        )
        self.file_label.grid(row=3, column=0, pady=(6, 14))

        btn_row = ctk.CTkFrame(drop_row, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.browse_btn = ctk.CTkButton(
            btn_row, text="", width=130, height=32, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=self._font(size=12), command=self._browse_for_file,
        )
        self.browse_btn.grid(row=0, column=0)

        self.specs_scroll = ctk.CTkFrame(
            card, fg_color=COLOR_CARD_INNER, corner_radius=12,
        )
        self.specs_scroll.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 20))
        for col in range(3):
            self.specs_scroll.grid_columnconfigure(col, weight=1)
        self._show_empty_specs()

    def _build_card_analytics(self, parent) -> None:
        card = self._card(parent, 1)
        card.grid_columnconfigure(1, weight=1)

        self._card_title(card, 0, "sp_header")

        layout = ctk.CTkFrame(card, fg_color="transparent")
        layout.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 16))
        layout.grid_columnconfigure(1, weight=1)

        cover_col = ctk.CTkFrame(layout, fg_color="transparent", width=150)
        cover_col.grid(row=0, column=0, sticky="nw", padx=(0, 18))
        cover_col.grid_propagate(False)

        self.sp_cover = ctk.CTkLabel(
            cover_col, text="", width=COVER_DISPLAY_SIZE, height=COVER_DISPLAY_SIZE,
            fg_color=COLOR_CARD_INNER, corner_radius=10,
        )
        self.sp_cover.pack(anchor="w")
        self.sp_cover.pack_forget()

        self.sp_cover_dl_btn = ctk.CTkButton(
            cover_col,
            text="",
            width=COVER_DISPLAY_SIZE,
            height=24,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLOR_SURFACE_ALT,
            border_width=0,
            text_color=COLOR_ACCENT,
            font=self._font(size=10),
            command=self._download_cover,
        )
        self.sp_cover_dl_btn.pack(anchor="w", pady=(6, 0))
        self.sp_cover_dl_btn.pack_forget()

        metrics_col = ctk.CTkFrame(layout, fg_color="transparent")
        metrics_col.grid(row=0, column=1, sticky="nsew")
        metrics_col.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(metrics_col, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top_row.grid_columnconfigure(0, weight=1)

        status_block = ctk.CTkFrame(top_row, fg_color="transparent")
        status_block.grid(row=0, column=0, sticky="ew")
        status_block.grid_columnconfigure(0, weight=1)

        self.sp_status = ctk.CTkLabel(
            status_block, text="",
            font=self._font(size=12), text_color=COLOR_MUTED, anchor="w",
        )
        self.sp_status.grid(row=0, column=0, sticky="w")

        self.sp_fallback_warn = ctk.CTkLabel(
            status_block, text="",
            font=self._font(size=10), text_color=COLOR_WARNING,
            anchor="w", wraplength=520, justify="left",
        )
        self.sp_fallback_warn.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.sp_fallback_warn.grid_remove()

        self.sp_open_btn = ctk.CTkButton(
            top_row, text="", width=150, height=30, corner_radius=10,
            fg_color=COLOR_SPOTIFY, hover_color=COLOR_SPOTIFY_HOVER,
            text_color="#ffffff", font=self._font(size=11, weight="bold"),
            command=self._open_spotify,
        )
        self.sp_open_btn.grid(row=0, column=1, sticky="ne", padx=(8, 0))
        self.sp_open_btn.grid_remove()

        body = ctk.CTkFrame(metrics_col, fg_color=COLOR_CARD_INNER, corner_radius=12)
        body.grid(row=1, column=0, sticky="ew")
        for col in range(3):
            body.grid_columnconfigure(col, weight=1, uniform="sp_col")

        col1 = ctk.CTkFrame(body, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=10)
        col2 = ctk.CTkFrame(body, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)
        col3 = ctk.CTkFrame(body, fg_color="transparent")
        col3.grid(row=0, column=2, sticky="nsew", padx=(6, 12), pady=10)

        # Column 1 — release metadata
        self.sp_label_key = self._mk_compact_label(col1, 0)
        self.sp_label_val = self._mk_compact_value(col1, 1)
        self.sp_release_key = self._mk_compact_label(col1, 2)
        self.sp_release_val = self._mk_compact_value(col1, 3)
        self.sp_dist_key = self._mk_compact_label(col1, 4)
        self.sp_dist_val = self._mk_compact_value(col1, 5)

        # Column 2 — mood & analytics
        self.sp_mood_key = self._mk_compact_label(col2, 0)
        self.sp_mood_val = self._mk_compact_value(col2, 1)
        self.sp_bpm_key = self._mk_compact_label(col2, 2)
        self.sp_bpm_val = self._mk_compact_value(col2, 3)
        self.sp_key_key = self._mk_compact_label(col2, 4)
        self.sp_key_val = self._mk_compact_value(col2, 5)
        self.sp_pop_key = self._mk_compact_label(col2, 6)
        self.sp_pop_val = self._mk_compact_value(col2, 7)

        # Column 3 — identifiers & YouTube
        self.sp_isrc_key = self._mk_compact_label(col3, 0)
        self.sp_isrc_val = self._mk_compact_value(col3, 1)
        self.sp_upc_key = self._mk_compact_label(col3, 2)
        self.sp_upc_val = self._mk_compact_value(col3, 3)
        self.sp_ytviews_key = self._mk_compact_label(col3, 4)
        self.sp_ytviews_val = self._mk_compact_value(col3, 5)
        self.sp_ytchan_key = self._mk_compact_label(col3, 6)
        self.sp_ytchan_val = self._mk_compact_value(col3, 7)
        self.sp_ytpub_key = self._mk_compact_label(col3, 8)
        self.sp_ytpub_val = self._mk_compact_value(col3, 9)

        metrics_row = ctk.CTkFrame(body, fg_color="transparent")
        metrics_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 10))
        metrics_row.grid_columnconfigure(1, weight=1)
        metrics_row.grid_columnconfigure(4, weight=1)

        self.sp_energy_key = self._mk_field_label(metrics_row, 0, 0)
        self.sp_energy_bar = ctk.CTkProgressBar(
            metrics_row, height=10, corner_radius=5,
            progress_color=COLOR_ACCENT, fg_color=COLOR_BORDER,
        )
        self.sp_energy_bar.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=8)
        self.sp_energy_bar.set(0)
        self.sp_energy_val = self._mk_field_value(metrics_row, 0, 2)

        self.sp_dance_key = ctk.CTkLabel(
            metrics_row, text="", font=self._font(size=12, weight="bold"),
            text_color=COLOR_MUTED, anchor="w",
        )
        self.sp_dance_key.grid(row=0, column=3, sticky="w", padx=(0, 8), pady=8)
        self.sp_dance_bar = ctk.CTkProgressBar(
            metrics_row, height=10, corner_radius=5,
            progress_color=COLOR_ACCENT, fg_color=COLOR_BORDER,
        )
        self.sp_dance_bar.grid(row=0, column=4, sticky="ew", padx=(0, 10), pady=8)
        self.sp_dance_bar.set(0)
        self.sp_dance_val = self._mk_field_value(metrics_row, 0, 5)

        self.sp_note = ctk.CTkLabel(
            metrics_col, text="",
            font=self._font(size=10), text_color=COLOR_MUTED,
            anchor="w", wraplength=MAX_CONTENT_WIDTH - 180, justify="left",
        )
        self.sp_note.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.sp_note.grid_remove()

    def _build_card_actions(self, parent) -> None:
        card = self._card(parent, 2)

        self._card_title(card, 0, "card_action_title_lbl")

        ai_block = ctk.CTkFrame(card, fg_color=COLOR_CARD_INNER, corner_radius=12)
        ai_block.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
        ai_block.grid_columnconfigure(0, weight=1)

        self.analyze_btn = ctk.CTkButton(
            ai_block, text="", width=240, height=42, corner_radius=12,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff", font=self._font(size=14, weight="bold"),
            command=self._start_ai_analysis,
        )
        self.analyze_btn.grid(row=0, column=0, pady=(16, 8))

        self.progress_bar = ctk.CTkProgressBar(
            ai_block, width=420, height=10, corner_radius=5,
            progress_color=COLOR_ACCENT, fg_color=COLOR_BORDER,
        )
        self.progress_bar.grid(row=1, column=0, pady=(0, 6))
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        self.progress_label = ctk.CTkLabel(
            ai_block, text="", font=self._font(size=11), text_color=COLOR_MUTED,
        )
        self.progress_label.grid(row=2, column=0, pady=(0, 4))

        self.ai_result_label = ctk.CTkLabel(
            ai_block, text="", font=self._font(size=13), text_color=COLOR_MUTED,
            wraplength=680, justify="left", anchor="w",
        )
        self.ai_result_label.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 16))

        convert_block = ctk.CTkFrame(card, fg_color=COLOR_CARD_INNER, corner_radius=12)
        convert_block.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 12))
        convert_block.grid_columnconfigure(2, weight=1)

        self.convert_format_label = ctk.CTkLabel(
            convert_block, text="",
            font=self._font(size=12, weight="bold"), text_color=COLOR_MUTED, anchor="w",
        )
        self.convert_format_label.grid(row=0, column=0, sticky="w", padx=(16, 10), pady=14)

        self.convert_format_var = ctk.StringVar(value="WAV")
        self.convert_format_menu = ctk.CTkOptionMenu(
            convert_block, values=["WAV", "FLAC", "MP3"],
            variable=self.convert_format_var, width=120, height=34, corner_radius=10,
            fg_color=COLOR_SURFACE, button_color=COLOR_BORDER,
            button_hover_color=COLOR_MUTED, dropdown_fg_color=COLOR_SURFACE,
            text_color=COLOR_TEXT, font=self._font(size=12),
        )
        self.convert_format_menu.grid(row=0, column=1, sticky="w", pady=14)

        self.convert_btn = ctk.CTkButton(
            convert_block, text="", width=170, height=34, corner_radius=10,
            fg_color=COLOR_SURFACE, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=self._font(size=12, weight="bold"), command=self._convert_audio,
        )
        self.convert_btn.grid(row=0, column=3, sticky="e", padx=(0, 16), pady=14)

        pitch_row = ctk.CTkFrame(card, fg_color="transparent")
        pitch_row.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 12))

        self.sp_desc_btn = ctk.CTkButton(
            pitch_row, text="", height=34, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff", font=self._font(size=12, weight="bold"),
            command=self._open_description,
        )
        self.sp_desc_btn.grid(row=0, column=0, padx=(0, 8))

        self.sp_songdna_btn = ctk.CTkButton(
            pitch_row, text="", height=34, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=self._font(size=12), command=self._open_songdna,
        )
        self.sp_songdna_btn.grid(row=0, column=1, padx=(0, 8))

        self.sp_youtube_btn = ctk.CTkButton(
            pitch_row, text="", height=34, corner_radius=10,
            fg_color=COLOR_YOUTUBE, hover_color=COLOR_YOUTUBE_HOVER,
            text_color="#ffffff", font=self._font(size=12, weight="bold"),
            command=self._open_youtube_search,
        )
        self.sp_youtube_btn.grid(row=0, column=2)

        self.about_btn = ctk.CTkButton(
            card, text="", height=40, corner_radius=12,
            fg_color=COLOR_SURFACE, hover_color=COLOR_SURFACE_ALT,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=self._font(size=13, weight="bold"), command=self._open_about,
        )
        self.about_btn.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 10))

        self.demo_btn = ctk.CTkButton(
            card, text="", height=48, corner_radius=14,
            fg_color=COLOR_DEMO, hover_color=COLOR_DEMO_HOVER,
            text_color="#ffffff", font=self._font(size=14, weight="bold"),
            command=self._open_demo_form,
        )
        self.demo_btn.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 20))

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 8))
        header.grid_columnconfigure(1, weight=1)

        if self._logo_image is not None:
            self.logo_label = ctk.CTkLabel(
                header, image=self._logo_image, text="",
            )
            self.logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=1, sticky="w")
        title_block.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            title_block,
            text="",
            font=self._font(size=28, weight="bold"),
            text_color=COLOR_TEXT,
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="",
            font=self._font(size=13),
            text_color=COLOR_MUTED,
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.lang_var = ctk.StringVar(
            value=language_label_for_code(self.current_lang)
        )
        self.lang_menu = ctk.CTkOptionMenu(
            header,
            values=list(LANGUAGE_OPTIONS.keys()),
            variable=self.lang_var,
            command=self._on_language_selected,
            width=150,
            height=34,
            corner_radius=10,
            fg_color=COLOR_SURFACE,
            button_color=COLOR_SURFACE_ALT,
            button_hover_color=COLOR_BORDER,
            dropdown_fg_color=COLOR_SURFACE,
            dropdown_hover_color=COLOR_SURFACE_ALT,
            text_color=COLOR_TEXT,
            font=self._font(size=12),
        )
        self.lang_menu.grid(row=0, column=2, rowspan=2, sticky="e", padx=(16, 0))

    def _mk_field_label(self, parent, row: int, col: int) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text="", font=self._font(size=12, weight="bold"),
            text_color=COLOR_MUTED, anchor="w",
        )
        lbl.grid(row=row, column=col, sticky="w", padx=(14, 8), pady=8)
        return lbl

    def _mk_field_value(self, parent, row: int, col: int) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text="—", font=self._font(size=13),
            text_color=COLOR_TEXT, anchor="w",
        )
        lbl.grid(row=row, column=col, sticky="w", padx=(0, 12), pady=8)
        return lbl

    def _mk_compact_label(self, parent, row: int) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text="", font=self._font(size=11, weight="bold"),
            text_color=COLOR_MUTED, anchor="w",
        )
        lbl.grid(row=row, column=0, sticky="w", pady=(8, 0))
        return lbl

    def _mk_compact_value(self, parent, row: int) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text="—", font=self._font(size=12),
            text_color=COLOR_TEXT, anchor="w", wraplength=220, justify="left",
        )
        lbl.grid(row=row, column=0, sticky="w", pady=(0, 2))
        return lbl

    def _open_demo_form(self) -> None:
        webbrowser.open(DEMO_FORM_URL)

    def _convert_audio(self) -> None:
        if not self.current_file:
            messagebox.showinfo(
                self._t("msg_no_file_title"), self._t("msg_no_file_body")
            )
            return

        fmt = self.convert_format_var.get().upper()
        ext_map = {"WAV": ".wav", "FLAC": ".flac", "MP3": ".mp3"}
        ext = ext_map.get(fmt, ".wav")
        stem = Path(self.current_file).stem

        save_path = filedialog.asksaveasfilename(
            title=self._t("convert_button"),
            defaultextension=ext,
            initialfile=f"{stem}{ext}",
            filetypes=[
                (self._t("file_dialog_wav"), "*.wav"),
                (self._t("file_dialog_mp3"), "*.mp3"),
                (self._t("file_dialog_flac"), "*.flac"),
                (self._t("file_dialog_all"), "*.*"),
            ],
        )
        if not save_path:
            return

        try:
            if not configure_pydub_ffmpeg():
                messagebox.showerror(
                    self._t("convert_error_title"),
                    self._t("convert_ffmpeg_error"),
                )
                return

            audio = AudioSegment.from_file(self.current_file)
            export_kwargs = {}
            if fmt == "MP3":
                export_kwargs["bitrate"] = "320k"
            audio.export(save_path, format=fmt.lower(), **export_kwargs)
            messagebox.showinfo(
                self._t("convert_success_title"),
                self._t("convert_success_body", path=save_path),
            )
        except Exception as exc:
            err_text = str(exc).lower()
            if "ffmpeg" in err_text or "winerror 2" in err_text or "not found" in err_text:
                messagebox.showerror(
                    self._t("convert_error_title"),
                    self._t("convert_ffmpeg_error"),
                )
            else:
                messagebox.showerror(
                    self._t("convert_error_title"),
                    self._t("convert_error_body", error=exc),
                )

    def _download_cover(self) -> None:
        if not check_internet_connection():
            messagebox.showinfo(
                self._t("cover_error_title"), self._t("offline_warning")
            )
            return
        artist, title = _split_artist_title(
            (self.spotify_result or {}).get("matched_name") or self._search_query()
        )
        spotify_url = (self.spotify_result or {}).get("cover_url")
        url = search_hi_res_artwork_url(artist, title) or spotify_url
        if not url:
            messagebox.showinfo(
                self._t("cover_error_title"), self._t("cover_no_url")
            )
            return

        ext = ".png" if ".png" in url.lower() else ".jpg"
        default_name = f"{artist} - {title} cover".strip(" -")
        if default_name in ("— - — cover", "cover", "— cover"):
            default_name = "cover_art"

        save_path = filedialog.asksaveasfilename(
            title=self._t("btn_download_cover"),
            defaultextension=ext,
            initialfile=f"{default_name}{ext}",
            filetypes=[
                ("JPEG", "*.jpg;*.jpeg"),
                ("PNG", "*.png"),
                (self._t("file_dialog_all"), "*.*"),
            ],
        )
        if not save_path:
            return

        data = download_artwork(url)
        if not data and spotify_url and url != spotify_url:
            data = download_artwork(spotify_url)
        if not data and spotify_url:
            try:
                req = urllib.request.Request(
                    spotify_url, headers={"User-Agent": "MerphiAudioInspector/1.0"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
            except Exception:
                data = None

        if not data:
            messagebox.showerror(
                self._t("cover_error_title"),
                self._t("cover_error_body", error="Download failed"),
            )
            return

        try:
            with open(save_path, "wb") as fh:
                fh.write(data)
            messagebox.showinfo(
                self._t("cover_saved_title"),
                self._t("cover_saved_body", path=save_path),
            )
        except Exception as exc:
            messagebox.showerror(
                self._t("cover_error_title"),
                self._t("cover_error_body", error=exc),
            )

    # ------------------------------------------------------------------
    # Spotify insights
    # ------------------------------------------------------------------

    def _open_spotify(self) -> None:
        if self.spotify_url:
            webbrowser.open(self.spotify_url)

    def _start_spotify_lookup(self, filepath: str) -> None:
        self.spotify_result = None
        self.spotify_url = None
        self.spotify_token += 1
        token = self.spotify_token

        self.youtube_result = None
        self.youtube_url = None
        self.youtube_pending = False

        self.sp_open_btn.grid_remove()
        self.sp_note.grid_remove()
        self.sp_fallback_warn.grid_remove()
        self.sp_cover.pack_forget()
        self.sp_cover_dl_btn.pack_forget()
        self._cover_image = None

        if not check_internet_connection():
            self._set_offline_mode(True)
            self.sp_status.configure(
                text=self._t("offline_warning"), text_color=COLOR_WARNING
            )
            for val in (
                self.sp_label_val, self.sp_release_val, self.sp_mood_val,
                self.sp_bpm_val, self.sp_energy_val, self.sp_dance_val,
                self.sp_key_val, self.sp_pop_val, self.sp_isrc_val,
                self.sp_upc_val, self.sp_dist_val,
                self.sp_ytviews_val, self.sp_ytchan_val, self.sp_ytpub_val,
            ):
                val.configure(text="—")
            self.sp_energy_bar.set(0)
            self.sp_dance_bar.set(0)
            thread = threading.Thread(
                target=self._run_offline_lookup, args=(filepath, token), daemon=True
            )
            thread.start()
            return

        self._set_offline_mode(False)
        self.youtube_pending = YouTubeClient.enabled()
        self.sp_status.configure(
            text=self._t("spotify_searching"), text_color=COLOR_MUTED
        )
        for val in (
            self.sp_label_val, self.sp_release_val, self.sp_mood_val,
            self.sp_bpm_val, self.sp_energy_val, self.sp_dance_val,
            self.sp_key_val, self.sp_pop_val, self.sp_isrc_val,
            self.sp_upc_val, self.sp_dist_val,
            self.sp_ytviews_val, self.sp_ytchan_val, self.sp_ytpub_val,
        ):
            val.configure(text="…")
        self.sp_energy_bar.set(0)
        self.sp_dance_bar.set(0)

        thread = threading.Thread(
            target=self._run_spotify_lookup, args=(filepath, token), daemon=True
        )
        thread.start()

        # Safety net: never let the panel sit on "searching" forever.
        self.after(20000, lambda t=token: self._spotify_watchdog(t))

    def _run_offline_lookup(self, filepath: str, token: int) -> None:
        """Local librosa analysis only — no streaming API calls."""
        insights = SpotifyInsights.get()
        meta = {
            "found": False,
            "offline": True,
            "features": None,
            "features_pending": True,
        }
        try:
            features = insights.local_features(filepath)
        except Exception:
            features = None
        self.after(0, lambda: self._on_spotify_meta(meta, token))
        self.after(0, lambda: self._on_spotify_features(features, token))
        self.after(0, lambda: self._on_youtube(None, token))

    def _spotify_watchdog(self, token: int) -> None:
        if token != self.spotify_token:
            return
        if self.spotify_result is None:
            self.spotify_result = {
                "found": False, "error": "timeout",
                "features": None, "features_pending": False,
            }
            self._render_spotify()

    def _run_spotify_lookup(self, filepath: str, token: int) -> None:
        if not check_internet_connection():
            self.after(0, lambda: self._set_offline_mode(True))
            self._run_offline_lookup(filepath, token)
            return

        insights = SpotifyInsights.get()

        # Phase 0: ACRCloud acoustic fingerprint (authoritative if it matches).
        acr = None
        acr_enabled = ACRCloudClient.enabled()
        try:
            if acr_enabled:
                acr = ACRCloudClient.get().identify(filepath)
        except Exception:
            acr = None

        acr_matched = bool(acr and acr.get("matched"))

        # Phase 1: Spotify metadata — ISRC-exact after an ACR match, else text.
        try:
            if acr_matched and acr.get("isrc"):
                display = " — ".join(
                    p for p in (acr.get("artist"), acr.get("title")) if p
                )
                meta = insights.search_by_isrc(acr["isrc"], display)
                meta["found"] = True
                meta["source"] = "acrcloud"
                if display:
                    meta["matched_name"] = display
                if not meta.get("isrc"):
                    meta["isrc"] = acr.get("isrc")
                if not meta.get("label") and acr.get("label"):
                    meta["label"] = acr.get("label")
                if not meta.get("upc") and acr.get("upc"):
                    meta["upc"] = acr.get("upc")
            else:
                meta = insights.search_metadata(filepath)
                meta["source"] = "text"
                if acr_enabled and not acr_matched:
                    meta["text_search_fallback"] = True
        except Exception as exc:
            meta = {"found": False, "error": str(exc)}
        self.after(0, lambda: self._on_spotify_meta(meta, token))

        # Phase 2: slower local audio analysis (librosa).
        try:
            features = insights.local_features(filepath)
        except Exception:
            features = None
        self.after(0, lambda: self._on_spotify_features(features, token))

        # Phase 3: YouTube data (views / channel / upload date).
        youtube = None
        try:
            if YouTubeClient.enabled():
                if acr_matched:
                    yt_query = " ".join(
                        p for p in (acr.get("artist"), acr.get("title")) if p
                    )
                else:
                    yt_query = meta.get("query") or build_search_query(filepath)
                youtube = YouTubeClient.get().fetch(yt_query)
        except Exception:
            youtube = None
        self.after(0, lambda: self._on_youtube(youtube, token))

    def _on_spotify_meta(self, meta: dict, token: int) -> None:
        # Ignore stale results if a newer file was loaded meanwhile.
        if token != self.spotify_token:
            return
        meta = dict(meta)
        meta["features"] = None
        meta["features_pending"] = True
        self.spotify_result = meta
        self.spotify_url = meta.get("url")
        self._render_spotify()

    def _on_spotify_features(self, features: dict | None, token: int) -> None:
        if token != self.spotify_token:
            return
        if self.spotify_result is None:
            self.spotify_result = {"found": False}
        self.spotify_result["features"] = features
        self.spotify_result["features_pending"] = False
        self._render_spotify()

    def _on_youtube(self, youtube: dict | None, token: int) -> None:
        if token != self.spotify_token:
            return
        self.youtube_pending = False
        self.youtube_result = youtube
        self.youtube_url = youtube.get("url") if youtube else None
        self._render_youtube()

    def _render_youtube(self) -> None:
        na = self._t("na")
        yt = self.youtube_result

        if self.youtube_pending:
            for v in (self.sp_ytviews_val, self.sp_ytchan_val, self.sp_ytpub_val):
                v.configure(text="…")
            return

        if yt and yt.get("found"):
            views = yt.get("views")
            self.sp_ytviews_val.configure(
                text=format_views(views) if views is not None else na
            )
            self.sp_ytchan_val.configure(text=yt.get("channel") or na)
            self.sp_ytpub_val.configure(text=yt.get("published") or na)
            yt_dist = yt.get("distributor")
            if yt_dist and self.spotify_result:
                current = self.spotify_result.get("distributor")
                if not current or current == self._t("na"):
                    self.sp_dist_val.configure(text=yt_dist)
        else:
            placeholder = "—" if not self.file_loaded else na
            for v in (self.sp_ytviews_val, self.sp_ytchan_val, self.sp_ytpub_val):
                v.configure(text=placeholder)

    def _render_spotify(self) -> None:
        """Render the stored Spotify result in the current language."""
        result = self.spotify_result

        # Idle state (no file looked up yet).
        if result is None:
            if not self.file_loaded:
                self.sp_status.configure(
                    text=self._t("spotify_idle"), text_color=COLOR_MUTED
                )
            for val in (
                self.sp_label_val, self.sp_release_val, self.sp_mood_val,
                self.sp_bpm_val, self.sp_energy_val, self.sp_dance_val,
                self.sp_key_val, self.sp_pop_val, self.sp_isrc_val,
                self.sp_upc_val, self.sp_dist_val,
            ):
                val.configure(text="—")
            self.sp_energy_bar.set(0)
            self.sp_dance_bar.set(0)
            self.sp_open_btn.grid_remove()
            self.sp_note.grid_remove()
            self.sp_fallback_warn.grid_remove()
            self.sp_cover.pack_forget()
            self.sp_cover_dl_btn.pack_forget()
            self._render_youtube()
            return

        na = self._t("na")
        not_found = self._t("spotify_not_found")

        # Status line
        if result.get("found"):
            found_key = (
                "spotify_found_acr" if result.get("source") == "acrcloud"
                else "spotify_found"
            )
            self.sp_status.configure(
                text=self._t(found_key, name=result.get("matched_name") or ""),
                text_color=COLOR_SUCCESS,
            )
            if result.get("text_search_fallback"):
                self.sp_fallback_warn.configure(text=self._t("text_search_fallback"))
                self.sp_fallback_warn.grid()
            else:
                self.sp_fallback_warn.grid_remove()
            self.sp_label_val.configure(text=result.get("label") or na)
            self.sp_release_val.configure(text=result.get("release_date") or na)
            pop = result.get("popularity")
            self.sp_pop_val.configure(
                text=f"{pop} / 100" if pop is not None else na
            )
            self.sp_isrc_val.configure(text=result.get("isrc") or na)
            self.sp_upc_val.configure(text=result.get("upc") or na)
            self.sp_dist_val.configure(text=result.get("distributor") or na)
            self._render_cover(result.get("cover_bytes"))
            self._maybe_trigger_mmg_easter_egg(result)
            if self.spotify_url:
                self.sp_open_btn.grid()
            else:
                self.sp_open_btn.grid_remove()
        else:
            error = result.get("error")
            if result.get("offline"):
                self.sp_status.configure(
                    text=self._t("offline_warning"), text_color=COLOR_WARNING
                )
            elif error == "rate_limited":
                self.sp_status.configure(
                    text=self._t("spotify_rate_limited"), text_color=COLOR_WARNING
                )
            elif error:
                self.sp_status.configure(
                    text=self._t("spotify_error"), text_color=COLOR_WARNING
                )
            else:
                self.sp_status.configure(text=not_found, text_color=COLOR_MUTED)
            if result.get("text_search_fallback"):
                self.sp_fallback_warn.configure(text=self._t("text_search_fallback"))
                self.sp_fallback_warn.grid()
            else:
                self.sp_fallback_warn.grid_remove()
            self.sp_label_val.configure(text=not_found)
            self.sp_release_val.configure(text=not_found)
            self.sp_pop_val.configure(text=na if error else not_found)
            self.sp_isrc_val.configure(text=na if error else not_found)
            self.sp_upc_val.configure(text=na if error else not_found)
            self.sp_dist_val.configure(text=na if error else not_found)
            self.sp_open_btn.grid_remove()
            self._render_cover(None)

        # Audio features (Spotify if available, else local).
        features = result.get("features")
        if features:
            bpm = features.get("bpm") or 0
            energy = float(features.get("energy") or 0.0)
            dance = float(features.get("danceability") or 0.0)
            positive = features.get("valence_positive", True)

            self.sp_bpm_val.configure(text=f"{bpm} BPM" if bpm else na)
            self.sp_mood_val.configure(
                text=self._t("mood_positive") if positive else self._t("mood_dark"),
                text_color=COLOR_SUCCESS if positive else COLOR_WARNING,
            )
            self.sp_energy_bar.set(energy)
            self.sp_energy_val.configure(text=f"{round(energy * 100)}%")
            self.sp_dance_bar.set(dance)
            self.sp_dance_val.configure(text=f"{round(dance * 100)}%")

            key = features.get("key")
            camelot = features.get("camelot")
            if key and camelot:
                self.sp_key_val.configure(text=f"{key} · {camelot}")
            elif key:
                self.sp_key_val.configure(text=key)
            else:
                self.sp_key_val.configure(text=na)

            source = features.get("source", "local")
            if source == "local":
                self.sp_note.configure(text=self._t("spotify_note_local"))
                self.sp_note.grid()
            else:
                self.sp_note.grid_remove()
        else:
            placeholder = "…" if result.get("features_pending") else na
            for val in (self.sp_bpm_val, self.sp_mood_val,
                        self.sp_energy_val, self.sp_dance_val, self.sp_key_val):
                val.configure(text=placeholder)
            self.sp_mood_val.configure(text_color=COLOR_TEXT)
            self.sp_energy_bar.set(0)
            self.sp_dance_bar.set(0)
            self.sp_note.grid_remove()

        self._render_youtube()

    def _render_cover(self, cover_bytes) -> None:
        if not cover_bytes:
            self.sp_cover.pack_forget()
            self.sp_cover_dl_btn.pack_forget()
            self._cover_image = None
            return
        try:
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(cover_bytes)).convert("RGB")
            self._cover_image = ctk.CTkImage(
                light_image=img, size=(COVER_DISPLAY_SIZE, COVER_DISPLAY_SIZE)
            )
            self.sp_cover.configure(image=self._cover_image, text="")
            self.sp_cover.pack()
            self.sp_cover_dl_btn.pack(pady=(6, 0))
        except Exception:
            self.sp_cover.pack_forget()
            self.sp_cover_dl_btn.pack_forget()
            self._cover_image = None

    # ------------------------------------------------------------------
    # YouTube / description / Song DNA
    # ------------------------------------------------------------------

    def _search_query(self) -> str:
        res = self.spotify_result or {}
        query = res.get("query")
        if not query and self.current_file:
            query = build_search_query(self.current_file)
        return query or ""

    def _open_youtube_search(self) -> None:
        # Prefer the exact matched video; otherwise open a YouTube search.
        if self.youtube_url:
            webbrowser.open(self.youtube_url)
            return
        query = self._search_query()
        if not query:
            messagebox.showinfo(
                self._t("msg_no_file_title"), self._t("msg_no_file_body")
            )
            return
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        webbrowser.open(url)

    def _description_data(self) -> dict:
        res = self.spotify_result or {}
        feat = res.get("features") or {}
        matched = res.get("matched_name") or self._search_query() or "—"
        artist, track_title = _split_artist_title(matched)
        link = self.spotify_url or self.youtube_url or "—"
        return {
            "title": matched,
            "artist": artist if artist != "—" else None,
            "track_title": track_title if track_title != "—" else matched,
            "label": res.get("label"),
            "distributor": res.get("distributor"),
            "release_date": res.get("release_date"),
            "isrc": res.get("isrc"),
            "upc": res.get("upc"),
            "popularity": res.get("popularity"),
            "bpm": feat.get("bpm"),
            "key": feat.get("key"),
            "camelot": feat.get("camelot"),
            "energy": feat.get("energy"),
            "dance": feat.get("danceability"),
            "mood_positive": feat.get("valence_positive", True),
            "link": link,
        }

    def _copy_to_clipboard(self, text: str, button: ctk.CTkButton) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        button.configure(text=self._t("copied"))
        self.after(1500, lambda: button.configure(text=self._t("copy_button")))

    def _make_popup(self, title: str, width: int, height: int) -> ctk.CTkToplevel:
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry(f"{width}x{height}")
        win.configure(fg_color=COLOR_BG)
        win.transient(self)
        win.lift()
        _apply_window_icon(win)
        win.after(50, win.focus)
        return win

    def _open_about(self) -> None:
        win = self._make_popup(self._t("about_title"), 520, 360)
        win.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(win, fg_color=COLOR_ACCENT, corner_radius=0, height=88)
        hero.grid(row=0, column=0, sticky="ew")
        hero.grid_propagate(False)
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hero, text=self._t("about_title"),
            font=self._font(size=20, weight="bold"), text_color="#ffffff",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 4))
        ctk.CTkLabel(
            hero, text="Merphi Audio Inspector",
            font=self._font(size=12), text_color="#f3e8ff",
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 18))

        body = ctk.CTkFrame(
            win, fg_color=COLOR_SURFACE, corner_radius=14,
            border_width=1, border_color=COLOR_BORDER,
        )
        body.grid(row=1, column=0, sticky="nsew", padx=22, pady=(18, 12))
        body.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            body, text=self._t("about_body"),
            font=self._font(size=14), text_color=COLOR_TEXT,
            wraplength=430, justify="left", anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 16))

        links = ctk.CTkFrame(body, fg_color="transparent")
        links.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 18))
        links.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            links, text=self._t("about_website_btn"), height=36, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_ACCENT,
            font=self._font(size=12, weight="bold"),
            command=lambda: webbrowser.open(ABOUT_WEBSITE_URL),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            links, text=self._t("about_smartlink_btn"), height=36, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_ACCENT,
            font=self._font(size=12, weight="bold"),
            command=lambda: webbrowser.open(ABOUT_SMARTLINK_URL),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ctk.CTkButton(
            win, text=self._t("close_button"), width=110, height=34, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=self._font(size=12), command=win.destroy,
        ).grid(row=2, column=0, sticky="e", padx=22, pady=(0, 18))

    def _open_description(self) -> None:
        if not self.current_file:
            messagebox.showinfo(
                self._t("msg_no_file_title"), self._t("msg_no_file_body")
            )
            return

        text = generate_track_description(
            self.current_lang, self._description_data(), t_func=self._t
        )

        win = self._make_popup(self._t("desc_title"), 620, 420)
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            win, text=self._t("desc_title"),
            font=self._font(size=16, weight="bold"), text_color=COLOR_TEXT,
            wraplength=540, justify="left",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        box = ctk.CTkTextbox(
            win, font=self._font(size=13), fg_color=COLOR_SURFACE,
            text_color=COLOR_TEXT, wrap="word", corner_radius=10,
        )
        box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        box.insert("1.0", text)
        box.configure(state="disabled")

        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="e", padx=18, pady=(0, 16))
        copy_btn = ctk.CTkButton(
            bar, text=self._t("copy_button"), width=120, height=34, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#ffffff",
            font=self._font(size=12, weight="bold"),
        )
        copy_btn.configure(command=lambda: self._copy_to_clipboard(text, copy_btn))
        copy_btn.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            bar, text=self._t("close_button"), width=100, height=34, corner_radius=10,
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER, text_color=COLOR_TEXT,
            border_width=1, border_color=COLOR_BORDER, font=self._font(size=12),
            command=win.destroy,
        ).grid(row=0, column=1)

    def _songdna_tree_section(
        self, parent, row: int, title: str, items: list[tuple[str, str]]
    ) -> int:
        section = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER,
        )
        section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            section, text=title,
            font=self._font(size=13, weight="bold"), text_color=COLOR_ACCENT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))

        inner = ctk.CTkFrame(section, fg_color=COLOR_SURFACE_ALT, corner_radius=8)
        inner.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        inner.grid_columnconfigure(1, weight=1)

        for i, (label_text, value_text) in enumerate(items):
            ctk.CTkLabel(
                inner, text=f"  ▸ {label_text}",
                font=self._font(size=11, weight="bold"),
                text_color=COLOR_MUTED, anchor="w", width=170,
            ).grid(row=i, column=0, sticky="w", padx=(8, 8), pady=6)
            ctk.CTkLabel(
                inner, text=str(value_text),
                font=self._font(size=12), text_color=COLOR_TEXT,
                anchor="w", wraplength=320, justify="left",
            ).grid(row=i, column=1, sticky="w", padx=(0, 10), pady=6)

        return row + 1

    def _open_songdna(self) -> None:
        if not self.current_file:
            messagebox.showinfo(
                self._t("msg_no_file_title"), self._t("msg_no_file_body")
            )
            return

        res = self.spotify_result or {}
        feat = res.get("features") or {}
        na = self._t("na")

        def fmt_pct(v):
            return f"{round(float(v) * 100)}%" if v is not None else na

        key = feat.get("key")
        camelot = feat.get("camelot")
        key_text = f"{key} · {camelot}" if key and camelot else (key or na)
        mood = na
        if feat:
            mood = self._t("mood_positive") if feat.get("valence_positive", True) \
                else self._t("mood_dark")
        bpm = feat.get("bpm")
        matched = res.get("matched_name") or self._search_query() or na
        artist, track_title = _split_artist_title(matched)
        if artist == "—":
            artist = matched

        release_items = [
            (self._t("spotify_label"), res.get("label") or na),
            (self._t("spotify_distributor"), res.get("distributor") or na),
            (self._t("spotify_release"), res.get("release_date") or na),
        ]
        yt = self.youtube_result or {}
        if yt.get("distributor"):
            release_items.append(
                (self._t("youtube_distributor"), yt.get("distributor"))
            )
        track_items = [
            (self._t("credits_artist"), artist),
            (self._t("songdna_track_name"), track_title if track_title != "—" else matched),
        ]
        id_items = [
            (self._t("spotify_isrc"), res.get("isrc") or na),
            (self._t("spotify_upc"), res.get("upc") or na),
        ]
        analytics_items = [
            (self._t("spotify_popularity"),
             f"{res.get('popularity')} / 100" if res.get("popularity") is not None else na),
            (self._t("spotify_key"), key_text),
            (self._t("spotify_bpm"), f"{bpm} BPM" if bpm else na),
            (self._t("spotify_mood"), mood),
            (self._t("spotify_energy"), fmt_pct(feat.get("energy"))),
            (self._t("spotify_danceability"), fmt_pct(feat.get("danceability"))),
        ]

        win = self._make_popup(self._t("songdna_title"), 520, 680)
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(win, fg_color=COLOR_BG)
        scroll.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        scroll.grid_columnconfigure(0, weight=1)

        r = 0
        if self._cover_image is not None:
            ctk.CTkLabel(scroll, image=self._cover_image, text="").grid(
                row=r, column=0, pady=(4, 12)
            )
            r += 1

        ctk.CTkLabel(
            scroll, text=self._t("songdna_title"),
            font=self._font(size=16, weight="bold"), text_color=COLOR_TEXT,
            wraplength=440, justify="left",
        ).grid(row=r, column=0, sticky="w", pady=(0, 12))
        r += 1

        r = self._songdna_tree_section(
            scroll, r, self._t("songdna_section_release"), release_items
        )
        r = self._songdna_tree_section(
            scroll, r, self._t("songdna_section_track"), track_items
        )
        r = self._songdna_tree_section(
            scroll, r, self._t("songdna_section_identifiers"), id_items
        )
        r = self._songdna_tree_section(
            scroll, r, self._t("songdna_section_analytics"), analytics_items
        )

        if yt.get("found"):
            views = yt.get("views")
            yt_items = [
                (self._t("youtube_views"),
                 format_views(views) if views is not None else na),
                (self._t("youtube_channel"), yt.get("channel") or na),
                (self._t("youtube_published"), yt.get("published") or na),
            ]
            r = self._songdna_tree_section(
                scroll, r, self._t("songdna_section_youtube"), yt_items
            )

        yt_credits = yt.get("credits") or []
        if yt_credits:
            credit_items = []
            for line in yt_credits:
                if ":" in line:
                    label, val = line.split(":", 1)
                    credit_items.append((label.strip(), val.strip()))
                else:
                    credit_items.append((line, ""))
            r = self._songdna_tree_section(
                scroll, r, self._t("songdna_section_credits"), credit_items
            )

        yt_writers = yt.get("writers") or []
        if yt_writers:
            writer_items = [(name, "") for name in yt_writers]
            r = self._songdna_tree_section(
                scroll, r, self._t("songdna_section_writers"), writer_items
            )

        disclaimer = ctk.CTkFrame(
            scroll, fg_color=COLOR_SURFACE_ALT, corner_radius=10,
            border_width=1, border_color=COLOR_BORDER,
        )
        disclaimer.grid(row=r, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkLabel(
            disclaimer, text=self._t("credits_note"),
            font=self._font(size=11), text_color=COLOR_MUTED,
            anchor="w", wraplength=440, justify="left",
        ).pack(fill="x", padx=14, pady=12)

    def _on_language_selected(self, choice: str) -> None:
        self.current_lang = LANGUAGE_OPTIONS[choice]
        self._apply_language()

    def _apply_language(self) -> None:
        self.title(self._t("app_title"))
        self.title_label.configure(text=self._t("app_title"))
        self.subtitle_label.configure(text=self._t("subtitle"))
        self.drop_hint.configure(text=self._t("drop_hint"))
        self.browse_btn.configure(text=self._t("browse_button"))
        self.card_file_title_lbl.configure(text=self._t("card_file_title"))
        self.card_action_title_lbl.configure(text=self._t("card_action_title"))
        self.analyze_btn.configure(text=self._t("analyze_button"))
        self.about_btn.configure(text=self._t("about_btn"))
        self.demo_btn.configure(text=self._t("demo_button"))
        self.convert_format_label.configure(text=self._t("convert_format_label"))
        self.convert_btn.configure(text=self._t("convert_button"))
        self.sp_cover_dl_btn.configure(text=self._t("btn_download_cover"))

        self.sp_header.configure(text=self._t("spotify_header"))
        self.sp_label_key.configure(text=self._t("spotify_label"))
        self.sp_release_key.configure(text=self._t("spotify_release"))
        self.sp_mood_key.configure(text=self._t("spotify_mood"))
        self.sp_bpm_key.configure(text=self._t("spotify_bpm"))
        self.sp_energy_key.configure(text=self._t("spotify_energy"))
        self.sp_dance_key.configure(text=self._t("spotify_danceability"))
        self.sp_key_key.configure(text=self._t("spotify_key"))
        self.sp_pop_key.configure(text=self._t("spotify_popularity"))
        self.sp_isrc_key.configure(text=self._t("spotify_isrc"))
        self.sp_upc_key.configure(text=self._t("spotify_upc"))
        self.sp_dist_key.configure(text=self._t("spotify_distributor"))
        self.sp_ytviews_key.configure(text=self._t("youtube_views"))
        self.sp_ytchan_key.configure(text=self._t("youtube_channel"))
        self.sp_ytpub_key.configure(text=self._t("youtube_published"))
        self.sp_open_btn.configure(text=self._t("spotify_open_btn"))
        self.sp_songdna_btn.configure(text=self._t("btn_songdna"))
        self.sp_desc_btn.configure(text=self._t("btn_description"))
        self.sp_youtube_btn.configure(text=self._t("btn_youtube"))
        self._update_offline_banner()
        self._render_spotify()

        if self.file_loaded:
            self.drop_label.configure(text=self._t("file_loaded_success"))
            if self.current_file:
                self.file_label.configure(text=self.current_file)
        else:
            self.drop_label.configure(text=self._t("drop_primary"))
            self.file_label.configure(text=self._t("no_file_loaded"))

        if self.is_analyzing:
            pass
        elif self.ai_state == "complete" and self.last_ai_probability is not None:
            self._show_ai_result(self.last_ai_probability, update_only=True)
        elif self.file_loaded:
            self.ai_result_label.configure(text=self._t("ai_ready"), text_color=COLOR_MUTED)
        else:
            self.ai_result_label.configure(text=self._t("ai_idle"), text_color=COLOR_MUTED)

        if self.current_file:
            try:
                specs = self._extract_media_info(self.current_file)
                self._render_specs(specs)
            except Exception:
                self._show_empty_specs()
        else:
            self._show_empty_specs()

    # ------------------------------------------------------------------
    # Drag & drop / file loading
    # ------------------------------------------------------------------

    def _setup_drag_and_drop(self) -> None:
        if not WINDND_AVAILABLE:
            return

        def on_drop(files: list) -> None:
            if not files:
                return
            path = self._decode_dropped_path(files[0])
            self.after(0, lambda: self._load_file(path))

        windnd.hook_dropfiles(self, func=on_drop)

    @staticmethod
    def _decode_dropped_path(raw_path) -> str:
        if isinstance(raw_path, bytes):
            try:
                return raw_path.decode("utf-8")
            except UnicodeDecodeError:
                return raw_path.decode("mbcs")
        return str(raw_path)

    def _browse_for_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title=self._t("file_dialog_title"),
            filetypes=[
                (
                    self._t("file_dialog_audio"),
                    "*.wav *.mp3 *.flac",
                ),
                (self._t("file_dialog_wav"), "*.wav"),
                (self._t("file_dialog_mp3"), "*.mp3"),
                (self._t("file_dialog_flac"), "*.flac"),
                (self._t("file_dialog_all"), "*.*"),
            ],
        )
        if filepath:
            self._load_file(filepath)

    def _load_file(self, filepath: str) -> None:
        path = Path(filepath)

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            messagebox.showerror(
                self._t("msg_unsupported_title"),
                self._t(
                    "msg_unsupported_body",
                    extensions=", ".join(sorted(SUPPORTED_EXTENSIONS)),
                ),
            )
            return

        if not path.is_file():
            messagebox.showerror(
                self._t("msg_not_found_title"),
                self._t("msg_not_found_body"),
            )
            return

        self.current_file = str(path.resolve())
        self.file_loaded = True
        self.file_label.configure(text=self.current_file)
        self.drop_zone.configure(border_color=COLOR_ACCENT)
        self.drop_label.configure(text=self._t("file_loaded_success"))
        self._reset_ai_panel()

        try:
            specs = self._extract_media_info(self.current_file)
            self._render_specs(specs)
        except Exception as exc:
            messagebox.showerror(
                self._t("msg_mediainfo_title"),
                self._t("msg_mediainfo_body", error=exc),
            )
            self._show_empty_specs()

        self._start_spotify_lookup(self.current_file)

    # ------------------------------------------------------------------
    # MediaInfo extraction
    # ------------------------------------------------------------------

    def _extract_media_info(self, filepath: str) -> dict[str, str]:
        media_info = MediaInfo.parse(filepath)
        audio_track = next(
            (track for track in media_info.tracks if track.track_type == "Audio"),
            None,
        )

        if audio_track is None:
            raise ValueError("No audio track found in this file.")

        bit_depth = getattr(audio_track, "bit_depth", None)
        sampling_rate = getattr(audio_track, "sampling_rate", None)
        channels = getattr(audio_track, "channel_s", None) or getattr(
            audio_track, "channels", None
        )
        codec = (
            getattr(audio_track, "format", None)
            or getattr(audio_track, "codec_id", None)
            or self._t("unknown")
        )
        bit_rate = getattr(audio_track, "bit_rate", None)
        duration_ms = getattr(audio_track, "duration", None)
        daw_encoder = detect_daw_encoder(filepath) or self._t("na")

        return {
            "file_name": Path(filepath).name,
            "format": getattr(audio_track, "format", None)
            or path_suffix_label(filepath),
            "codec": str(codec),
            "bit_depth": (
                f"{bit_depth} {self._t('unit_bit')}" if bit_depth else self._t("na")
            ),
            "sampling_rate": format_sampling_rate(sampling_rate, self._t("na")),
            "channels": format_channels(
                channels,
                self._t("na"),
                self._t("unit_channel"),
                self._t("unit_channels"),
            ),
            "bitrate": format_bitrate(bit_rate, self._t("na")),
            "duration": format_duration(duration_ms, self._t("na")),
            "daw_encoder": daw_encoder,
        }

    def _show_empty_specs(self) -> None:
        placeholder = {key: "—" for key in SPEC_KEYS}
        self._render_specs(placeholder)

    def _render_specs(self, specs: dict[str, str]) -> None:
        self.current_specs = dict(specs)
        for widget in self.specs_scroll.winfo_children():
            widget.destroy()

        for col_index, keys in enumerate(SPEC_COLUMNS):
            col_frame = ctk.CTkFrame(self.specs_scroll, fg_color="transparent")
            col_frame.grid(row=0, column=col_index, sticky="nsew", padx=(8, 8), pady=8)

            for row_index, key in enumerate(keys):
                key_label = ctk.CTkLabel(
                    col_frame,
                    text=self._t(f"spec_{key}"),
                    font=self._font(size=11, weight="bold"),
                    text_color=COLOR_MUTED,
                    anchor="w",
                )
                key_label.grid(row=row_index * 2, column=0, sticky="w", pady=(6, 0))

                value_label = ctk.CTkLabel(
                    col_frame,
                    text=specs.get(key, "—"),
                    font=self._font(size=12),
                    text_color=COLOR_TEXT,
                    anchor="w",
                    wraplength=240,
                    justify="left",
                )
                value_label.grid(row=row_index * 2 + 1, column=0, sticky="w", pady=(0, 4))

    # ------------------------------------------------------------------
    # AI analysis (local Deezer deepfake-detector)
    # ------------------------------------------------------------------

    def _reset_ai_panel(self) -> None:
        self._stop_progress_pulse()
        self.ai_state = "ready"
        self.last_ai_probability = None
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()
        self.progress_label.configure(text="")
        self.ai_result_label.configure(
            text=self._t("ai_ready"),
            text_color=COLOR_MUTED,
        )
        self.analyze_btn.configure(state="normal")

    def _start_ai_analysis(self) -> None:
        if self.is_analyzing:
            return

        if not self.current_file:
            messagebox.showinfo(
                self._t("msg_no_file_title"),
                self._t("msg_no_file_body"),
            )
            return

        self.is_analyzing = True
        self.ai_state = "analyzing"
        self.analyze_btn.configure(state="disabled")
        self.progress_bar.grid()
        self.progress_bar.set(0.05)
        self.progress_label.configure(text=self._t("progress_loading_model"))
        self.ai_result_label.configure(text="", text_color=COLOR_MUTED)
        self._start_progress_pulse()

        thread = threading.Thread(target=self._run_ai_analysis, daemon=True)
        thread.start()

    def _start_progress_pulse(self) -> None:
        self._pulse_active = True
        self._pulse_direction = 1
        self._pulse_value = 0.05
        self._animate_progress_pulse()

    def _stop_progress_pulse(self) -> None:
        self._pulse_active = False
        if self._pulse_job is not None:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None

    def _animate_progress_pulse(self) -> None:
        if not self._pulse_active:
            return

        self._pulse_value += 0.035 * self._pulse_direction
        if self._pulse_value >= 0.92:
            self._pulse_direction = -1
        elif self._pulse_value <= 0.08:
            self._pulse_direction = 1

        self.progress_bar.set(self._pulse_value)
        self._pulse_job = self.after(60, self._animate_progress_pulse)

    def _run_ai_analysis(self) -> None:
        """Run local Deezer deepfake-detector inference off the UI thread."""
        filepath = self.current_file
        if not filepath:
            self.after(0, self._handle_ai_failure, "No file loaded.")
            return

        try:
            detector = DeezerDeepfakeDetector.get()
            self.after(
                0,
                lambda: self.progress_label.configure(
                    text=self._t("progress_loading_model")
                ),
            )
            detector.ensure_ready()

            self.after(
                0,
                lambda: self.progress_label.configure(
                    text=self._t("progress_running_model")
                ),
            )
            probability = detector.predict_file(filepath)
            self.after(0, lambda p=probability: self._show_ai_result(p))
        except ModelNotReadyError as exc:
            self.after(0, self._handle_model_missing, str(exc))
        except Exception as exc:
            self.after(0, self._handle_ai_failure, str(exc))

    def _handle_model_missing(self, error: str) -> None:
        self._stop_progress_pulse()
        self.is_analyzing = False
        self.ai_state = "ready"
        self.analyze_btn.configure(state="normal")
        self.progress_bar.grid_remove()
        self.progress_label.configure(text="")
        self.ai_result_label.configure(text=self._t("ai_ready"), text_color=COLOR_MUTED)
        messagebox.showerror(
            self._t("msg_model_missing_title"),
            self._t("msg_model_missing_body"),
        )

    def _handle_ai_failure(self, error: str) -> None:
        self._stop_progress_pulse()
        self.is_analyzing = False
        self.ai_state = "ready"
        self.analyze_btn.configure(state="normal")
        self.progress_bar.grid_remove()
        self.progress_label.configure(text="")
        self.ai_result_label.configure(text=self._t("ai_ready"), text_color=COLOR_MUTED)
        messagebox.showerror(
            self._t("msg_ai_error_title"),
            self._t("msg_ai_error_body", error=error),
        )

    def _show_ai_result(self, probability: float, update_only: bool = False) -> None:
        if not update_only:
            self._stop_progress_pulse()
            self.is_analyzing = False
            self.analyze_btn.configure(state="normal")
            self.progress_bar.set(1)
            self.progress_label.configure(text=self._t("ai_complete"))

        self.ai_state = "complete"
        self.last_ai_probability = probability
        probability_percent = int(round(probability * 100))
        verdict_key = "verdict_ai" if probability >= 0.5 else "verdict_human"
        result_text = self._t(
            "ai_result",
            probability=probability_percent,
            verdict=self._t(verdict_key),
        )

        color = COLOR_SUCCESS if probability < 0.5 else COLOR_WARNING
        self.ai_result_label.configure(text=result_text, text_color=color)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _tag_value_to_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    text = str(value).strip()
    return text or None


def detect_daw_encoder(filepath: str) -> str:
    """Detect the DAW / encoder from tags, WAV RIFF chunks, and MediaInfo."""
    candidates: list[str] = []
    candidates.extend(_daw_from_mutagen(filepath))
    if str(filepath).lower().endswith(".wav"):
        candidates.extend(_daw_from_wav_chunks(filepath))
    candidates.extend(_daw_from_mediainfo(filepath))

    seen: set[str] = set()
    unique: list[str] = []
    for cand in candidates:
        cand = (cand or "").strip()
        if cand and cand not in seen:
            seen.add(cand)
            unique.append(cand)

    if not unique:
        return ""

    # Prefer a candidate that looks like a real DAW.
    for cand in unique:
        if any(daw in cand.lower() for daw in KNOWN_DAWS):
            return cand
    return unique[0]


def _daw_from_mutagen(filepath: str) -> list[str]:
    try:
        audio = MutagenFile(filepath, easy=False)
    except Exception:
        return []
    if audio is None:
        return []
    tags = getattr(audio, "tags", None)
    if not tags:
        return []

    matches: list[str] = []

    def consider(key: str, value) -> None:
        key_norm = str(key).lower().replace("_", "").replace("-", "")
        if any(hint in key_norm for hint in SOFTWARE_TAG_HINTS):
            text = _tag_value_to_str(value)
            if text and text not in matches:
                matches.append(text)

    if hasattr(tags, "items"):
        for key, value in tags.items():
            consider(key, value)

    for frame_id in ("TENC", "TSSE", "TSOF"):
        if hasattr(tags, "get"):
            frame_value = tags.get(frame_id)
            if frame_value is not None:
                text = _tag_value_to_str(frame_value)
                if text and text not in matches:
                    matches.append(text)
    return matches


def _daw_from_wav_chunks(filepath: str) -> list[str]:
    """Read DAW info from WAV RIFF 'INFO/ISFT' and Broadcast-WAV 'bext' chunks."""
    results: list[str] = []
    try:
        with open(filepath, "rb") as f:
            header = f.read(12)
            if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
                return results

            while True:
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break
                chunk_id = chunk_header[0:4]
                size = int.from_bytes(chunk_header[4:8], "little")

                if chunk_id == b"bext":
                    data = f.read(size)
                    if len(data) >= 288:
                        originator = (
                            data[256:288].split(b"\x00")[0]
                            .decode("latin-1", "ignore").strip()
                        )
                        if originator:
                            results.append(originator)
                elif chunk_id == b"LIST":
                    data = f.read(size)
                    if data[0:4] == b"INFO":
                        pos = 4
                        while pos + 8 <= len(data):
                            sub_id = data[pos:pos + 4]
                            sub_size = int.from_bytes(data[pos + 4:pos + 8], "little")
                            pos += 8
                            value = data[pos:pos + sub_size]
                            pos += sub_size + (sub_size & 1)
                            if sub_id in (b"ISFT", b"ITCH", b"IENG", b"ICMT"):
                                text = (
                                    value.split(b"\x00")[0]
                                    .decode("latin-1", "ignore").strip()
                                )
                                if text:
                                    results.append(text)
                else:
                    # Skip the chunk body (e.g. the large 'data' chunk).
                    f.seek(size, 1)

                if size & 1:  # chunks are word-aligned (pad byte for odd sizes)
                    f.seek(1, 1)
    except Exception:
        return results
    return results


def _daw_from_mediainfo(filepath: str) -> list[str]:
    out: list[str] = []
    try:
        media_info = MediaInfo.parse(filepath)
        for track in media_info.tracks:
            if track.track_type != "General":
                continue
            for attr in (
                "writing_application", "encoded_application",
                "encoded_library", "encoded_library_name", "producer",
            ):
                value = getattr(track, attr, None)
                if value:
                    out.append(str(value))
    except Exception:
        pass
    return out


def path_suffix_label(filepath: str) -> str:
    return Path(filepath).suffix.upper().replace(".", "") or "Unknown"


def format_sampling_rate(value, na_label: str = "N/A") -> str:
    if not value:
        return na_label
    try:
        rate = int(float(value))
        return f"{rate:,} Hz"
    except (TypeError, ValueError):
        return str(value)


def format_channels(
    value,
    na_label: str = "N/A",
    channel_label: str = "channel",
    channels_label: str = "channels",
) -> str:
    if value is None:
        return na_label
    if isinstance(value, str):
        return value
    try:
        count = int(value)
        label = channel_label if count == 1 else channels_label
        return f"{count} {label}"
    except (TypeError, ValueError):
        return str(value)


def format_bitrate(value, na_label: str = "N/A") -> str:
    if not value:
        return na_label
    try:
        bps = int(float(value))
        if bps >= 1_000_000:
            return f"{bps / 1_000_000:.2f} Mbps"
        return f"{bps / 1_000:.0f} kbps"
    except (TypeError, ValueError):
        return str(value)


def format_duration(duration_ms, na_label: str = "N/A") -> str:
    if not duration_ms:
        return na_label
    try:
        total_seconds = int(float(duration_ms) / 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:d}:{seconds:02d}"
    except (TypeError, ValueError):
        return str(duration_ms)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = MerphiAudioInspector()
    try:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    except ImportError:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
