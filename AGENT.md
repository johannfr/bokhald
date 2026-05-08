# Bokhald - Agent Context

## Overview

Bokhald is a personal accounting/budgeting application for projecting cash flow. It tracks recurring transactions (income and bills), projects running balances months into the future, and helps determine how much monthly injection is needed to stay above a safety margin.

## Tech Stack

- **Python 3.12**
- **NiceGUI** — web UI framework (renders in browser, opens automatically)
- **SQLAlchemy** — ORM (mapped_column style, declarative base)
- **SQLite** — local database stored at `~/.local/share/bokhald/bokhald.db`
- **Alembic** — database migrations
- **Babel / gettext** — i18n (all user-facing strings use `_()`)
- **Nix flake** (nixpkgs 25.11) — build system, `nix build` to verify

## Project Structure

```
bokhald/
├── flake.nix
├── pyproject.toml                (build-backend = setuptools.build_meta)
├── babel.cfg
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 8cb3aa67ffb6_initial_schema.py
│       ├── 9119de706bcb_add_payee_to_recurring_transactions.py
│       └── a3f1c8d92e4a_add_amount_changes_table.py
├── src/bokhald/
│   ├── __init__.py
│   ├── main.py                   (entry point, inits DB, runs migrations, starts NiceGUI)
│   ├── db.py                     (engine/session factory, DB path)
│   ├── models.py                 (Account, PaymentMethod, RecurringTransaction, ActualAmount, AmountChange)
│   ├── seed.py                   (seeds 5 default payment methods)
│   ├── logic.py                  (parse_months, build_projection, calculate_recommended_injection)
│   └── ui/
│       ├── __init__.py
│       ├── main_view.py          (main spreadsheet view)
│       ├── accounts.py           (account CRUD dialog)
│       ├── payments.py           (payment method CRUD dialog)
│       └── transactions.py       (transaction CRUD, open_transaction_edit as top-level function)
```

## Data Model

### Account
- `name`, `initial_balance`, `safety_margin` (fixed amount), `is_default`

### PaymentMethod
- `name`, `description`, `url`
- 5 seeded: Krafa, Automatic transfer, Credit card, Paypal, Google Play

### RecurringTransaction
- `name`, `payee`, `description`
- `amount` — positive = injection/income, negative = bill/subscription
- `is_estimate` — if true, cells are italic and clickable for actual amounts
- `day_of_month`, `months_active` (pattern like "1-12" or "1-3,7,12")
- `payment_method_id` (required), `account_id`
- `is_internal`, `target_account_id` — for internal transfers (double-entry)
- `start_year`, `start_month`, `end_year`, `end_month`
- `deactivated_at` — soft delete (nullable datetime)
- Cascade deletes to ActualAmount and AmountChange

### ActualAmount
- `recurring_transaction_id`, `year`, `month`, `actual_amount`
- Unique on `(recurring_transaction_id, year, month)`
- Tracks what was actually paid on estimate transactions

### AmountChange
- `recurring_transaction_id`, `effective_year`, `effective_month`, `amount`
- Unique on `(recurring_transaction_id, effective_year, effective_month)`
- Overrides the transaction's base amount from the effective date forward
- The transaction's `amount` field is the initial amount; changes override it chronologically

## Key Design Decisions

- **Unified model:** Both income (injections) and expenses (bills) are `RecurringTransaction` — distinguished by sign of `amount`
- **Soft delete:** `deactivated_at` field. Hard delete is also available via the Delete button in the edit dialog.
- **Internal transfers:** Double-entry. Source account sees the negative amount, target account sees `abs(amount)` as positive.
- **Payment method required** for ALL transactions including injections
- **Date field order:** smallest to largest (day, month, year) in all UI
- **Default payment method:** "Krafa" is pre-selected for new transactions
- **Sorting:** Injections first, then bills. Within each group: sorted by payee, then name.
- **Amount changes:** The projection engine resolves the effective amount per month by finding the latest AmountChange on or before that month, falling back to `txn.amount`.
- **Estimate cells:** Italic in spreadsheet, clickable to enter/remove actual amounts. Saving empty value removes the actual.
- **i18n:** All strings wrapped in `_()` for Icelandic translation readiness
- **No manual SQL:** Everything goes through SQLAlchemy ORM

## UI Architecture

### Main Spreadsheet View (`main_view.py`)
- Table with months as columns, year headers spanning months
- Rows: recommended injection (blue), injections (green), bills (red), running balance (bottom)
- Current month highlighted, view scrolls to center it on load
- Sticky left column with transaction names (clickable to edit)
- Estimate cells are italic and clickable to enter actual amounts
- Account tabs at the top, show_inactive checkbox
- Scrolling uses JS setTimeout (not ui.timer) to avoid parent slot errors

### Transaction Edit Dialog (`transactions.py: open_transaction_edit`)
- Standalone top-level function, callable from both the transactions list and the spreadsheet
- All fields for the transaction
- "Amount Changes" section for existing transactions (list + add form)
- Deactivate/Reactivate button
- Delete button with confirmation dialog
- Receives `on_save_callback` to refresh the caller's view

### Transactions List Dialog (`transactions.py: open_transactions_dialog`)
- 900px wide card with all transactions listed
- Each row: payee-name, amount, type, account, payment method, estimate/fixed, edit button (same line)
- Show/hide inactive checkbox
- "New Transaction" button

## Build & Run

```bash
nix build          # verify it compiles
nix run            # run the application (opens browser)
alembic upgrade head   # apply migrations (also done automatically on startup)
```

## Future Considerations

- **Centralized database:** The app uses SQLAlchemy so switching to Postgres is trivial (change connection string, add psycopg2 dependency). Neon (serverless Postgres) recommended for cheap hosted option.
- **i18n:** Babel configured, strings wrapped in `_()`, but no .po files generated yet.

## Common Patterns

- NiceGUI UI is built inside nested function closures that capture `session_factory`
- Data is detached from SQLAlchemy session into dicts before rendering (to avoid lazy-load issues outside session context)
- `spreadsheet_container.clear()` + rebuild pattern for refreshing views
- All dialogs follow: `with ui.dialog() as dialog, ui.card():` pattern, call `dialog.open()` at end
