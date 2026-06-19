"""
Generate Inno Setup assets with correct encodings and branding images.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
INSTALLER_DIR = PROJECT_ROOT / "installer"
ICON_PATH = PROJECT_ROOT / "icon.ico"
EULA_RU_PATH = INSTALLER_DIR / "EULA_ru.txt"
EULA_EN_PATH = INSTALLER_DIR / "EULA_en.txt"
LOGO_BMP_PATH = INSTALLER_DIR / "logo.bmp"

EULA_TEXT_RU = """ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ С КОНЕЧНЫМ ПОЛЬЗОВАТЕЛЕМ
Merphi Audio Inspector — Merphi Music Group

ВНИМАТЕЛЬНО ПРОЧИТАЙТЕ НАСТОЯЩЕЕ СОГЛАШЕНИЕ ПЕРЕД УСТАНОВКОЙ И ИСПОЛЬЗОВАНИЕМ ПРОГРАММЫ.

1. ПРЕДМЕТ СОГЛАШЕНИЯ
Настоящее соглашение регулирует установку и использование программного обеспечения «Merphi Audio Inspector», предназначенного для анализа, обработки и проверки аудиоматериалов в рамках деятельности Merphi Music Group.
(Остальные пункты соблюдать согласно стандартам использования корпоративного ПО).
© Merphi Music Group. Все права защищены."""

EULA_TEXT_EN = """END USER LICENSE AGREEMENT
Merphi Audio Inspector — Merphi Music Group

PLEASE READ THIS AGREEMENT CAREFULLY BEFORE INSTALLING OR USING THE SOFTWARE.

1. SUBJECT OF THE AGREEMENT
This agreement governs the installation and use of Merphi Audio Inspector, software
intended for analysis, processing, and verification of audio materials within the
operations of Merphi Music Group.
(All remaining terms follow standard corporate software usage policies.)
© Merphi Music Group. All rights reserved."""


def write_eula_files() -> None:
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    EULA_RU_PATH.write_text(EULA_TEXT_RU, encoding="windows-1251")
    EULA_EN_PATH.write_text(EULA_TEXT_EN, encoding="utf-8")
    print(f"Wrote EULA (windows-1251): {EULA_RU_PATH}")
    print(f"Wrote EULA (utf-8): {EULA_EN_PATH}")


def write_logo_bmp() -> None:
    if not ICON_PATH.is_file():
        raise FileNotFoundError(f"Missing icon: {ICON_PATH}")

    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(ICON_PATH) as img:
        logo = img.convert("RGB")
        logo = logo.resize((55, 55), Image.Resampling.LANCZOS)
        logo.save(LOGO_BMP_PATH, format="BMP")
    print(f"Wrote wizard logo: {LOGO_BMP_PATH}")


def main() -> None:
    write_eula_files()
    write_logo_bmp()


if __name__ == "__main__":
    main()
