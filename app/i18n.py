from __future__ import annotations

from typing import Dict
from app.core.config import settings

# מילון טקסטים לפי שפה ומפתח
# כרגע אנחנו משתמשים בזה בעיקר למסכי /language,
# אבל אפשר להרחיב בהמשך לכל ההודעות בבוט.
TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        "LANGUAGE_MENU_TITLE": "Choose your preferred language:",
        "LANGUAGE_SET_CONFIRM": "Your preferred language is now set to English.",
        "LANGUAGE_BUTTON_EN": "English 🇬🇧",
        "LANGUAGE_BUTTON_HE": "עברית 🇮🇱",
        "LANGUAGE_BUTTON_RU": "Русский 🇷🇺",
        "LANGUAGE_BUTTON_ES": "Español 🇪🇸",
        "LANGUAGE_SET_CONFIRM_HE": "Your preferred language is now set to Hebrew.",
        "LANGUAGE_SET_CONFIRM_RU": "Your preferred language is now set to Russian.",
        "LANGUAGE_SET_CONFIRM_ES": "Your preferred language is now set to Spanish.",
    },
    "he": {
        "LANGUAGE_MENU_TITLE": "בחר שפה מועדפת לבוט:",
        "LANGUAGE_SET_CONFIRM": "השפה המועדפת שלך עודכנה לעברית.",
        "LANGUAGE_BUTTON_EN": "English 🇬🇧",
        "LANGUAGE_BUTTON_HE": "עברית 🇮🇱",
        "LANGUAGE_BUTTON_RU": "Русский 🇷🇺",
        "LANGUAGE_BUTTON_ES": "Español 🇪🇸",
        "LANGUAGE_SET_CONFIRM_HE": "השפה המועדפת שלך עודכנה לעברית.",
        "LANGUAGE_SET_CONFIRM_RU": "השפה המועדפת שלך עודכנה לרוסית.",
        "LANGUAGE_SET_CONFIRM_ES": "השפה המועדפת שלך עודכנה לספרדית.",
    },
    "ru": {
        "LANGUAGE_MENU_TITLE": "Выберите предпочитаемый язык:",
        "LANGUAGE_SET_CONFIRM": "Ваш предпочтительный язык установлен на русский.",
        "LANGUAGE_BUTTON_EN": "English 🇬🇧",
        "LANGUAGE_BUTTON_HE": "עברית 🇮🇱",
        "LANGUAGE_BUTTON_RU": "Русский 🇷🇺",
        "LANGUAGE_BUTTON_ES": "Español 🇪🇸",
        "LANGUAGE_SET_CONFIRM_HE": "Ваш предпочтительный язык установлен на иврит.",
        "LANGUAGE_SET_CONFIRM_RU": "Ваш предпочтительный язык установлен на русский.",
        "LANGUAGE_SET_CONFIRM_ES": "Ваш предпочтительный язык установлен на испанский.",
    },
    "es": {
        "LANGUAGE_MENU_TITLE": "Elige tu idioma preferido:",
        "LANGUAGE_SET_CONFIRM": "Tu idioma preferido ahora es español.",
        "LANGUAGE_BUTTON_EN": "English 🇬🇧",
        "LANGUAGE_BUTTON_HE": "עברית 🇮🇱",
        "LANGUAGE_BUTTON_RU": "Русский 🇷🇺",
        "LANGUAGE_BUTTON_ES": "Español 🇪🇸",
        "LANGUAGE_SET_CONFIRM_HE": "Tu idioma preferido ahora es hebreo.",
        "LANGUAGE_SET_CONFIRM_RU": "Tu idioma preferido ahora es ruso.",
        "LANGUAGE_SET_CONFIRM_ES": "Tu idioma preferido ahora es español.",
    },
}


def _supported_from_env() -> set[str]:
    """
    מחלץ את רשימת השפות הנתמכות מתוך SUPPORTED_LANGUAGES,
    או מתוך TEXTS אם לא הוגדר.
    """
    env = (settings.SUPPORTED_LANGUAGES or "").strip()
    if env:
        parts = [p.strip().lower() for p in env.split(",") if p.strip()]
        return set(p for p in parts if p in TEXTS)
    # אם לא הוגדר – כל השפות המופיעות ב-TEXTS
    return set(TEXTS.keys())


SUPPORTED_LANGS = _supported_from_env()

DEFAULT_LANG = (settings.DEFAULT_LANGUAGE or "en").lower()
if DEFAULT_LANG not in TEXTS:
    DEFAULT_LANG = "en"


def normalize_lang(raw: str | None) -> str:
    """
    מחזיר קוד שפה תקין מתוך SUPPORTED_LANGS, או DEFAULT_LANG.
    תומך בקודים כמו he-IL, en-US וכו'.
    """
    if not raw:
        return DEFAULT_LANG

    lc = raw.lower()

    # טיפול בקודים נפוצים
    if lc in ("he", "iw", "he-il"):
        base = "he"
    elif lc.startswith("he-"):
        base = "he"
    elif lc in ("ru", "ru-ru"):
        base = "ru"
    elif lc.startswith("ru-"):
        base = "ru"
    elif lc in ("es", "es-es", "es-419"):
        base = "es"
    elif lc.startswith("es-"):
        base = "es"
    else:
        # ברירת מחדל – לפי החלק הראשון לפני '-'
        base = lc.split("-", 1)[0]

    if base in SUPPORTED_LANGS:
        return base
    if DEFAULT_LANG in SUPPORTED_LANGS:
        return DEFAULT_LANG
    # אם שום דבר לא מתאים – אנגלית
    return "en"


def t(lang: str, key: str) -> str:
    """
    מחזיר טקסט לפי שפה ומפתח.
    אם אין בשפה, ננסה באנגלית,
    ואם גם שם לא קיים – נחזיר את המפתח עצמו.
    """
    lang = normalize_lang(lang)
    if lang in TEXTS and key in TEXTS[lang]:
        return TEXTS[lang][key]

    if "en" in TEXTS and key in TEXTS["en"]:
        return TEXTS["en"][key]

    return key
