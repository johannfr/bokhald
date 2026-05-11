"""Bokhald main entry point."""

from __future__ import annotations

import os

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

    # Run all pending migrations (also creates tables on a fresh DB)
    command.upgrade(alembic_cfg, "head")

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

    dev_mode = os.environ.get("BOKHALD_DEV", "").lower() in ("1", "true", "yes")
    ui.run(host=HOST, port=PORT, title="Bokhald", reload=dev_mode, show=dev_mode)


if __name__ in {"__main__", "__mp_main__"}:
    main()
