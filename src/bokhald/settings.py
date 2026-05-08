"""Persistent settings for Bokhald."""

import json
from pathlib import Path

from bokhald.db import get_db_path

DEFAULTS = {
    "language": "en",
}


def _settings_path() -> Path:
    """Settings file lives alongside the database."""
    return get_db_path().parent / "settings.json"


def load_settings() -> dict:
    """Load settings from disk, returning defaults for missing keys."""
    path = _settings_path()
    settings = dict(DEFAULTS)
    if path.exists():
        try:
            with open(path) as f:
                settings.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings: dict) -> None:
    """Save settings to disk."""
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)


def get_setting(key: str):
    """Get a single setting value."""
    return load_settings().get(key, DEFAULTS.get(key))


def set_setting(key: str, value) -> None:
    """Set a single setting value and save."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
