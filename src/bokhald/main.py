"""Bokhald main entry point."""

from __future__ import annotations

import os
import threading
import webbrowser

from nicegui import app, ui

from bokhald.db import Base, get_engine, get_session_factory
from bokhald.i18n import set_language
from bokhald.models import Account, PaymentMethod, RecurringTransaction, ActualAmount  # noqa: F401
from bokhald.seed import seed_payment_methods
from bokhald.settings import get_setting


HOST = os.environ.get("BOKHALD_HOST", "127.0.0.1")
PORT = 8080


def init_db():
    """Initialize database, run migrations, and seed data."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")

    engine = get_engine()
    # Create all tables (in case no migrations exist yet)
    Base.metadata.create_all(engine)

    # Stamp with head if this is a fresh database
    try:
        command.stamp(alembic_cfg, "head")
    except Exception:
        pass

    # Seed default data
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_payment_methods(session)

    return session_factory


def main():
    """Run the Bokhald application."""
    session_factory = init_db()

    # Initialize language from saved settings
    lang = get_setting("language")
    set_language(lang)

    @ui.page("/")
    def index():
        ui.dark_mode(False)
        from bokhald.ui.main_view import create_main_view
        create_main_view(session_factory)

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://{HOST}:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    ui.run(host=HOST, port=PORT, title="Bokhald", reload=False, show=False)


if __name__ == "__main__":
    main()
