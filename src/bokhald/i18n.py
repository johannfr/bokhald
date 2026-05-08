"""Internationalization support for Bokhald."""

import gettext
import importlib.resources
from pathlib import Path

_current_translation: gettext.GNUTranslations | gettext.NullTranslations = gettext.NullTranslations()

AVAILABLE_LANGUAGES = {
    "en": "English",
    "is": "Íslenska",
}


def _get_locale_dir() -> str:
    """Get the path to the i18n directory."""
    # Try package resources first (for installed packages)
    try:
        ref = importlib.resources.files("bokhald") / "i18n"
        # Traverse to get actual filesystem path
        with importlib.resources.as_file(ref) as p:
            if p.is_dir():
                return str(p)
    except (TypeError, FileNotFoundError):
        pass

    # Fallback to relative path from this file
    return str(Path(__file__).parent / "i18n")


def set_language(lang: str) -> None:
    """Set the active language for gettext."""
    global _current_translation
    if lang == "en":
        _current_translation = gettext.NullTranslations()
    else:
        locale_dir = _get_locale_dir()
        try:
            _current_translation = gettext.translation(
                "messages", localedir=locale_dir, languages=[lang]
            )
        except FileNotFoundError:
            _current_translation = gettext.NullTranslations()

    # Install into builtins so gettext.gettext picks it up
    _current_translation.install()


def gettext_func(message: str) -> str:
    """Translate a message using the current translation."""
    return _current_translation.gettext(message)
