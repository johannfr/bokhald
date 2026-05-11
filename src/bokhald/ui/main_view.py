"""Main spreadsheet view for Bokhald."""

from __future__ import annotations

from datetime import date
from bokhald.i18n import gettext_func as _, AVAILABLE_LANGUAGES
from bokhald.settings import get_setting, set_setting

from nicegui import ui
from sqlalchemy.orm import Session

from bokhald.logic import build_projection, calculate_recommended_injection, MonthData
from bokhald.models import Account, ActualAmount, RecurringTransaction

# Month name abbreviations
MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def create_main_view(session_factory) -> None:
    """Create the main spreadsheet view."""

    def get_default_account(session: Session) -> Account | None:
        account = session.query(Account).filter(Account.is_default == True).first()  # noqa: E712
        if account is None:
            account = session.query(Account).first()
        return account

    def get_all_accounts(session: Session) -> list[Account]:
        return session.query(Account).order_by(Account.name).all()

    def render_spreadsheet(account_id: int) -> None:
        """Render the spreadsheet table for a given account."""
        spreadsheet_container.clear()

        with session_factory() as session:
            account = session.get(Account, account_id)
            if account is None:
                with spreadsheet_container:
                    ui.label(_("Account not found"))
                return

            projection = build_projection(session, account)
            recommended = calculate_recommended_injection(session, account)

            # Get all active transactions for this account
            owned_txns: list[RecurringTransaction] = (
                session.query(RecurringTransaction)
                .filter(RecurringTransaction.account_id == account_id)
                .order_by(RecurringTransaction.amount.desc())
                .all()
            )
            incoming_txns: list[RecurringTransaction] = (
                session.query(RecurringTransaction)
                .filter(
                    RecurringTransaction.target_account_id == account_id,
                    RecurringTransaction.is_internal == True,  # noqa: E712
                )
                .all()
            )

            all_txns = owned_txns + incoming_txns
            injections = [t for t in all_txns if t.amount > 0 or (t in incoming_txns)]
            bills = [t for t in all_txns if t.amount < 0 and t not in incoming_txns]

            if not projection:
                with spreadsheet_container:
                    ui.label(_("No data to display. Add some transactions first."))
                return

            # Find current month index for centering
            today = date.today()
            current_idx = 0
            for i, md in enumerate(projection):
                if md.year == today.year and md.month == today.month:
                    current_idx = i
                    break

            # Detach data before leaving session context
            txn_data = []
            for t in injections + bills:
                txn_data.append({
                    "id": t.id,
                    "name": t.name,
                    "payee": t.payee,
                    "description": t.description,
                    "amount": float(t.amount),
                    "is_estimate": t.is_estimate,
                    "is_injection": t.amount > 0 or t in incoming_txns,
                    "deactivated": t.deactivated_at is not None,
                    "day_of_month": t.day_of_month,
                    "months_active": t.months_active,
                    "payment_method_id": t.payment_method_id,
                    "account_id": t.account_id,
                    "is_internal": t.is_internal,
                    "target_account_id": t.target_account_id,
                    "start_year": t.start_year,
                    "start_month": t.start_month,
                    "end_year": t.end_year,
                    "end_month": t.end_month,
                })

            proj_data = []
            for md in projection:
                proj_data.append({
                    "year": md.year,
                    "month": md.month,
                    "amounts": dict(md.amounts),
                    "is_actual": dict(md.is_actual),
                    "balance": md.balance,
                })

        with spreadsheet_container:
            _build_table(proj_data, txn_data, recommended, current_idx, account_id, show_deactivated.value)

    def on_cell_click(txn_id: int, year: int, month: int, account_id: int):
        """Handle clicking a cell to enter actual amount."""
        with session_factory() as session:
            txn = session.get(RecurringTransaction, txn_id)
            if txn is None or not txn.is_estimate:
                return

            existing = (
                session.query(ActualAmount)
                .filter_by(recurring_transaction_id=txn_id, year=year, month=month)
                .first()
            )
            current_val = float(existing.actual_amount) if existing else None

        with ui.dialog() as dialog, ui.card():
            ui.label(f"{_('Enter actual amount for')} {MONTH_ABBR[month]} {year}")
            amount_input = ui.number(label=_("Amount"), value=current_val)

            with ui.row():
                def save():
                    with session_factory() as session:
                        existing = (
                            session.query(ActualAmount)
                            .filter_by(recurring_transaction_id=txn_id, year=year, month=month)
                            .first()
                        )
                        if amount_input.value is None:
                            # Empty value: remove actual amount, revert to estimate
                            if existing:
                                session.delete(existing)
                                session.commit()
                        elif existing:
                            existing.actual_amount = amount_input.value
                            session.commit()
                        else:
                            session.add(ActualAmount(
                                recurring_transaction_id=txn_id,
                                year=year,
                                month=month,
                                actual_amount=amount_input.value,
                            ))
                            session.commit()
                    dialog.close()
                    render_spreadsheet(account_id)

                ui.button(_("Save"), on_click=save)
                if current_val is not None:
                    def remove():
                        with session_factory() as session:
                            existing = (
                                session.query(ActualAmount)
                                .filter_by(recurring_transaction_id=txn_id, year=year, month=month)
                                .first()
                            )
                            if existing:
                                session.delete(existing)
                                session.commit()
                        dialog.close()
                        render_spreadsheet(account_id)
                    ui.button(_("Remove actual"), on_click=remove, color="red").props("flat")
                ui.button(_("Cancel"), on_click=dialog.close).props("flat")
        dialog.open()

    def on_name_click(txn: dict, account_id: int):
        """Handle clicking a transaction name to open the edit dialog."""
        from bokhald.ui.transactions import open_transaction_edit

        open_transaction_edit(
            session_factory,
            txn=txn,
            on_save_callback=lambda: render_spreadsheet(account_id),
        )

    def _build_table(
        proj_data: list[dict],
        txn_data: list[dict],
        recommended: float,
        current_idx: int,
        account_id: int,
        show_inactive: bool,
    ) -> None:
        """Build the HTML table for the spreadsheet view."""

        visible_txns = txn_data if show_inactive else [t for t in txn_data if not t["deactivated"]]
        injections = sorted(
            [t for t in visible_txns if t["is_injection"]],
            key=lambda t: (t["payee"] or "", t["name"]),
        )
        bills = sorted(
            [t for t in visible_txns if not t["is_injection"]],
            key=lambda t: (t["payee"] or "", t["name"]),
        )

        # Group months by year for the year header
        year_groups: list[tuple[int, int]] = []
        current_year = None
        count = 0
        for md in proj_data:
            if md["year"] != current_year:
                if current_year is not None:
                    year_groups.append((current_year, count))
                current_year = md["year"]
                count = 1
            else:
                count += 1
        if current_year is not None:
            year_groups.append((current_year, count))

        today = date.today()

        def _render_cell(txn, md, today, color, bg_normal, bg_current, account_id):
            """Render a single table cell for a transaction/month."""
            amount = md["amounts"].get(txn["id"])
            is_actual = md["is_actual"].get(txn["id"], False)
            if amount is not None:
                style_extra = "" if is_actual or not txn["is_estimate"] else "font-style: italic;"
                cell_text = f"{amount:,.0f}"
            else:
                style_extra = ""
                cell_text = ""
            is_current = md["year"] == today.year and md["month"] == today.month
            bg = bg_current if is_current else bg_normal
            clickable = txn["is_estimate"] and amount is not None
            cursor = "cursor: pointer;" if clickable else ""
            cell = ui.element("td").style(
                f"text-align: right; padding: 4px 8px; border: 1px solid #ddd; "
                f"color: {color}; background: {bg}; {style_extra} {cursor}"
            ).props(f'innerHTML="{cell_text}"')
            if clickable:
                cell.on("click", lambda _e, t=txn["id"], y=md["year"], m=md["month"]: on_cell_click(t, y, m, account_id))

        # Calculate scroll position to center current month
        col_width = 90
        scroll_x = max(0, (current_idx - 3) * col_width)

        with ui.element("div").style(
            f"overflow-x: auto; max-width: 100%; border: 1px solid #ddd; border-radius: 4px;"
        ).props(f'id="spreadsheet-scroll"') as scroll_div:
            # Use JavaScript to scroll to current month after render
            ui.run_javascript(
                f'setTimeout(() => {{ let el = document.getElementById("spreadsheet-scroll"); if (el) el.scrollLeft = {scroll_x}; }}, 100);'
            )

            with ui.element("table").style(
                "border-collapse: collapse; font-size: 13px; font-family: monospace;"
            ):
                # Year header row
                with ui.element("tr"):
                    ui.element("th").style(
                        "position: sticky; left: 0; z-index: 2; background: #f5f5f5; "
                        "min-width: 180px; padding: 4px 8px; border: 1px solid #ddd;"
                    ).props('innerHTML=""')
                    for year, span in year_groups:
                        ui.element("th").style(
                            f"text-align: center; background: #e8e8e8; padding: 4px; "
                            f"border: 1px solid #ddd; font-weight: bold;"
                        ).props(f'colspan="{span}" innerHTML="{year}"')

                # Month header row
                with ui.element("tr"):
                    ui.element("th").style(
                        "position: sticky; left: 0; z-index: 2; background: #f5f5f5; "
                        "min-width: 180px; padding: 4px 8px; border: 1px solid #ddd;"
                    ).props(f'innerHTML="{_("Name")}"')
                    for md in proj_data:
                        is_current = md["year"] == today.year and md["month"] == today.month
                        bg = "#fff3cd" if is_current else "#f5f5f5"
                        ui.element("th").style(
                            f"min-width: {col_width}px; text-align: right; padding: 4px 8px; "
                            f"border: 1px solid #ddd; background: {bg};"
                        ).props(f'innerHTML="{MONTH_ABBR[md["month"]]}"')

                # Recommended injection row
                with ui.element("tr").style("background: #e3f2fd;"):
                    ui.element("td").style(
                        "position: sticky; left: 0; z-index: 1; background: #e3f2fd; "
                        "padding: 4px 8px; border: 1px solid #ddd; font-weight: bold;"
                    ).props(f'innerHTML="{_("Recommended injection")}"')
                    for md in proj_data:
                        val = f"{recommended:,.0f}"
                        ui.element("td").style(
                            "text-align: right; padding: 4px 8px; border: 1px solid #ddd; "
                            "color: #1565c0; font-weight: bold;"
                        ).props(f'innerHTML="{val}"')

                # Injection rows (positive, green)
                for txn in injections:
                    opacity = "opacity: 0.5;" if txn["deactivated"] else ""
                    with ui.element("tr").style(opacity):
                        label = f"{txn['payee']} - {txn['name']}" if txn["payee"] else txn["name"]
                        if txn["deactivated"]:
                            label += f" ({_('inactive')})"
                        name_cell = ui.element("td").style(
                            "position: sticky; left: 0; z-index: 1; background: #e8f5e9; "
                            f"padding: 4px 8px; border: 1px solid #ddd; {opacity} "
                            "cursor: pointer; text-decoration: underline;"
                        ).props(f'innerHTML="{label}"')
                        name_cell.on("click", lambda _e, t=txn: on_name_click(t, account_id))
                        for md in proj_data:
                            _render_cell(txn, md, today, "#2e7d32", "#f1f8e9", "#dcedc8", account_id)

                # Bill rows (negative, red)
                for txn in bills:
                    opacity = "opacity: 0.5;" if txn["deactivated"] else ""
                    with ui.element("tr").style(opacity):
                        label = f"{txn['payee']} - {txn['name']}" if txn["payee"] else txn["name"]
                        if txn["deactivated"]:
                            label += f" ({_('inactive')})"
                        name_cell = ui.element("td").style(
                            "position: sticky; left: 0; z-index: 1; background: #ffebee; "
                            f"padding: 4px 8px; border: 1px solid #ddd; {opacity} "
                            "cursor: pointer; text-decoration: underline;"
                        ).props(f'innerHTML="{label}"')
                        name_cell.on("click", lambda _e, t=txn: on_name_click(t, account_id))
                        for md in proj_data:
                            _render_cell(txn, md, today, "#c62828", "#fce4ec", "#f8bbd0", account_id)

                # Balance row
                with ui.element("tr").style("font-weight: bold; border-top: 2px solid #333;"):
                    ui.element("td").style(
                        "position: sticky; left: 0; z-index: 1; background: #f5f5f5; "
                        "padding: 4px 8px; border: 1px solid #ddd; font-weight: bold;"
                    ).props(f'innerHTML="{_("Balance")}"')
                    for md in proj_data:
                        balance = md["balance"]
                        color = "#c62828" if balance < 0 else "#2e7d32"
                        is_current = md["year"] == today.year and md["month"] == today.month
                        bg = "#fff3cd" if is_current else "#f5f5f5"
                        ui.element("td").style(
                            f"text-align: right; padding: 4px 8px; border: 1px solid #ddd; "
                            f"color: {color}; background: {bg}; font-weight: bold;"
                        ).props(f'innerHTML="{balance:,.0f}"')

    # Main page layout
    from bokhald.ui.accounts import open_accounts_dialog
    from bokhald.ui.payments import open_payments_dialog
    from bokhald.ui.transactions import open_transactions_dialog

    def on_language_change(e):
        from bokhald.i18n import set_language
        set_language(e.value)
        set_setting("language", e.value)
        ui.navigate.reload()

    current_lang = get_setting("language")
    lang_options = {code: name for code, name in AVAILABLE_LANGUAGES.items()}

    with ui.left_drawer(value=False) as drawer:
        ui.button(_("Accounts"), on_click=lambda: open_accounts_dialog(session_factory, refresh)).classes('w-full')
        ui.button(_("Payment Methods"), on_click=lambda: open_payments_dialog(session_factory)).classes('w-full')
        ui.button(_("Transactions"), on_click=lambda: open_transactions_dialog(session_factory, refresh)).classes('w-full')
        ui.space()
        ui.separator().classes('q-my-sm')
        ui.select(lang_options, value=current_lang, on_change=on_language_change).classes('w-full')

    with ui.header().classes('items-center q-px-md'):
        ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat color=white')
        ui.label(_("Bokhald")).classes('text-h6 q-ml-sm')

    with ui.column().style("width: 100%; padding: 16px;"):

        show_deactivated = ui.checkbox(_("Show inactive transactions"), value=False)

        # Account tabs
        with session_factory() as session:
            accounts = get_all_accounts(session)
            default_account = get_default_account(session)

        account_tabs_container = ui.element("div")

        spreadsheet_container = ui.element("div").style("width: 100%;")

        def refresh():
            """Refresh everything."""
            nonlocal accounts, default_account
            with session_factory() as session:
                accounts = get_all_accounts(session)
                default_account = get_default_account(session)
            build_tabs()

        def build_tabs():
            account_tabs_container.clear()
            with account_tabs_container:
                if not accounts:
                    ui.label(_("No accounts yet. Create one to get started."))
                    return

                with ui.tabs().props("dense") as tabs:
                    tab_map = {}
                    for acc in accounts:
                        t = ui.tab(acc.name)
                        tab_map[acc.name] = acc.id

                with ui.tab_panels(tabs, on_change=lambda e: render_spreadsheet(tab_map.get(e.value, 0))):
                    for acc in accounts:
                        with ui.tab_panel(acc.name):
                            pass

                # Select default account
                if default_account:
                    tabs.set_value(default_account.name)
                    render_spreadsheet(default_account.id)

        show_deactivated.on_value_change(lambda: render_spreadsheet(
            default_account.id if default_account else 0
        ))

        build_tabs()
