# Bokhald

A personal accounting tool for projecting cash flow. You register your recurring income and bills, and it shows you a month-by-month spreadsheet of your balances going forward. The main thing it answers is: "how much do I need to transfer into this account each month so it doesn't run dry?"

## What it does

- Tracks recurring transactions (both income and expenses) per account
- Projects running balances months into the future
- Calculates a recommended monthly injection to stay above a configurable safety margin
- Supports multiple accounts with internal transfers (double-entry)
- Lets you record actual amounts for estimated bills (electricity, etc.) as they come in
- Handles transactions that only occur in certain months (e.g. "1-3,7,12")
- Amount changes over time (e.g. a subscription price increase from a certain month forward)

## How it works

The UI is a browser-based spreadsheet view built with NiceGUI. Months are columns, transactions are rows. Income rows are green, bills are red, and the recommended injection is blue at the top. The current month is centered on load and you can scroll horizontally to see the past and future.

Everything is stored in a local SQLite database at `~/.local/share/bokhald/bokhald.db`. Migrations run automatically on startup via Alembic.

## Tech stack

- Python 3.12
- NiceGUI (web UI)
- SQLAlchemy (ORM)
- SQLite (database)
- Alembic (migrations)
- Babel/gettext (i18n, strings are wrapped in `_()` but no translations exist yet)
- Nix flake (build system, uses nixpkgs 25.11)

## Building and running

You need Nix with flakes enabled.

```bash
nix build   # build the package
nix run     # run the app (opens in your default browser)
```

That's it. The database and migrations are handled automatically on first run.

## Development

Enter the dev shell:

```bash
nix develop
```

Run migrations manually if needed:

```bash
alembic upgrade head
```

## Project layout

```
src/bokhald/
  main.py           - entry point, starts NiceGUI
  db.py             - database engine/session setup
  models.py         - SQLAlchemy models (Account, RecurringTransaction, etc.)
  logic.py          - projection engine, injection calculation
  seed.py           - seeds default payment methods
  ui/
    main_view.py    - the main spreadsheet view
    accounts.py     - account management dialog
    payments.py     - payment method management dialog
    transactions.py - transaction CRUD dialogs

alembic/            - database migrations
flake.nix           - Nix build definition
pyproject.toml      - Python package metadata
```
