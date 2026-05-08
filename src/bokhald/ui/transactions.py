"""Recurring transaction management UI."""

from __future__ import annotations

from datetime import date, datetime
from gettext import gettext as _

from nicegui import ui

from bokhald.models import Account, AmountChange, PaymentMethod, RecurringTransaction


def open_transaction_edit(session_factory, txn: dict | None = None, on_save_callback=None) -> None:
    """Open edit/create dialog for a single recurring transaction.

    Can be called standalone (e.g. from the main spreadsheet view) or from the
    transactions list dialog.
    """
    is_new = txn is None

    # Load accounts and payment methods
    with session_factory() as session:
        accounts = session.query(Account).order_by(Account.name).all()
        account_options = {a.name: a.id for a in accounts}
        methods = session.query(PaymentMethod).order_by(PaymentMethod.name).all()
        method_options = {m.name: m.id for m in methods}

    if not accounts:
        ui.notify(_("Create an account first."), type="warning")
        return
    if not methods:
        ui.notify(_("No payment methods available."), type="warning")
        return

    with ui.dialog() as edit_dialog, ui.card().style("min-width: 500px;"):
        ui.label(_("New Transaction") if is_new else _("Edit Transaction")).style(
            "font-size: 18px; font-weight: bold;"
        )

        name_input = ui.input(label=_("Name"), value="" if is_new else txn["name"])
        payee_input = ui.input(label=_("Payee"), value="" if is_new else txn["payee"])
        desc_input = ui.textarea(label=_("Description"), value="" if is_new else txn["description"])

        with ui.row():
            amount_input = ui.number(
                label=_("Amount (positive=injection, negative=bill)"),
                value=0 if is_new else txn["amount"],
            )
            estimate_check = ui.checkbox(
                _("Estimate"),
                value=False if is_new else txn["is_estimate"],
            )

        with ui.row():
            day_input = ui.number(
                label=_("Day of month"),
                value=1 if is_new else txn["day_of_month"],
                min=1, max=31,
            )
            months_input = ui.input(
                label=_("Active months (e.g. 1-12, 1-3,7,12)"),
                value="1-12" if is_new else txn["months_active"],
            )

        account_select = ui.select(
            options=list(account_options.keys()),
            label=_("Account"),
            value=list(account_options.keys())[0] if is_new else next(
                (k for k, v in account_options.items() if v == txn["account_id"]), None
            ),
        )

        method_select = ui.select(
            options=list(method_options.keys()),
            label=_("Payment Method"),
            value="Krafa" if is_new and "Krafa" in method_options else (
                list(method_options.keys())[0] if is_new else next(
                    (k for k, v in method_options.items() if v == txn["payment_method_id"]), None
                )
            ),
        )

        internal_check = ui.checkbox(
            _("Internal transfer"),
            value=False if is_new else txn["is_internal"],
        )

        target_select = ui.select(
            options=list(account_options.keys()),
            label=_("Target Account"),
            value=None if is_new else next(
                (k for k, v in account_options.items() if v == txn.get("target_account_id")), None
            ),
        )
        target_select.bind_visibility_from(internal_check, "value")

        today = date.today()
        with ui.row():
            start_month_input = ui.number(
                label=_("Start month"),
                value=today.month if is_new else txn["start_month"],
                min=1, max=12,
            )
            start_year_input = ui.number(
                label=_("Start year"),
                value=today.year if is_new else txn["start_year"],
            )

        with ui.row():
            has_end = ui.checkbox(
                _("Has end date"),
                value=False if is_new else (txn["end_year"] is not None),
            )
            end_month_input = ui.number(
                label=_("End month"),
                value=12 if is_new or txn.get("end_month") is None else txn["end_month"],
                min=1, max=12,
            )
            end_year_input = ui.number(
                label=_("End year"),
                value=today.year if is_new or txn.get("end_year") is None else txn["end_year"],
            )
            end_month_input.bind_visibility_from(has_end, "value")
            end_year_input.bind_visibility_from(has_end, "value")

        # Amount changes history (only for existing transactions)
        if not is_new:
            ui.separator()
            ui.label(_("Amount Changes")).style("font-weight: bold; margin-top: 8px;")
            ui.label(_("Initial amount applies until the first change date.")).style("font-size: 12px; color: #666;")

            # Load existing amount changes
            with session_factory() as session:
                existing_changes = (
                    session.query(AmountChange)
                    .filter_by(recurring_transaction_id=txn["id"])
                    .order_by(AmountChange.effective_year, AmountChange.effective_month)
                    .all()
                )
                changes_data = [
                    {"id": ac.id, "year": ac.effective_year, "month": ac.effective_month, "amount": float(ac.amount)}
                    for ac in existing_changes
                ]

            changes_container = ui.column().style("width: 100%; gap: 4px;")

            def render_changes():
                changes_container.clear()
                with changes_container:
                    for ch in changes_data:
                        with ui.row().style("align-items: center; gap: 8px;"):
                            ui.label(f"{ch['month']:02d}/{ch['year']}").style("width: 60px;")
                            ui.label(f"{ch['amount']:,.0f}").style("width: 80px; text-align: right;")
                            def remove(ch_id=ch["id"], ch_ref=ch):
                                with session_factory() as session:
                                    obj = session.get(AmountChange, ch_id)
                                    if obj:
                                        session.delete(obj)
                                        session.commit()
                                changes_data.remove(ch_ref)
                                render_changes()
                            ui.button(icon="delete", on_click=remove).props("flat dense color=red")

            render_changes()

            # Add new amount change
            with ui.row().style("align-items: center; gap: 8px; margin-top: 8px;"):
                new_change_month = ui.number(label=_("Month"), value=today.month, min=1, max=12).style("width: 80px;")
                new_change_year = ui.number(label=_("Year"), value=today.year).style("width: 100px;")
                new_change_amount = ui.number(label=_("New amount")).style("width: 120px;")

                def add_change():
                    m = int(new_change_month.value)
                    y = int(new_change_year.value)
                    amt = new_change_amount.value
                    if amt is None:
                        ui.notify(_("Enter an amount"), type="warning")
                        return
                    with session_factory() as session:
                        # Check for duplicate
                        existing = (
                            session.query(AmountChange)
                            .filter_by(recurring_transaction_id=txn["id"], effective_year=y, effective_month=m)
                            .first()
                        )
                        if existing:
                            existing.amount = amt
                            session.commit()
                            # Update local data
                            for ch in changes_data:
                                if ch["id"] == existing.id:
                                    ch["amount"] = float(amt)
                                    break
                        else:
                            ac = AmountChange(
                                recurring_transaction_id=txn["id"],
                                effective_year=y,
                                effective_month=m,
                                amount=amt,
                            )
                            session.add(ac)
                            session.commit()
                            changes_data.append({"id": ac.id, "year": y, "month": m, "amount": float(amt)})
                            changes_data.sort(key=lambda c: (c["year"], c["month"]))
                    render_changes()

                ui.button(icon="add", on_click=add_change).props("flat dense")

        # Deactivation
        if not is_new:
            with ui.row():
                if txn["deactivated"]:
                    def reactivate():
                        with session_factory() as session:
                            t = session.get(RecurringTransaction, txn["id"])
                            t.deactivated_at = None
                            session.commit()
                        edit_dialog.close()
                        if on_save_callback:
                            on_save_callback()
                    ui.button(_("Reactivate"), on_click=reactivate, color="green")
                else:
                    def deactivate():
                        with session_factory() as session:
                            t = session.get(RecurringTransaction, txn["id"])
                            t.deactivated_at = datetime.utcnow()
                            session.commit()
                        edit_dialog.close()
                        if on_save_callback:
                            on_save_callback()
                    ui.button(_("Deactivate"), on_click=deactivate, color="red")

                def delete():
                    with ui.dialog() as confirm_dialog, ui.card():
                        ui.label(_("Are you sure you want to permanently delete this transaction?"))
                        ui.label(_("This will also delete all actual amounts and amount changes.")).style("font-size: 12px; color: #666;")
                        with ui.row():
                            def do_delete():
                                with session_factory() as session:
                                    t = session.get(RecurringTransaction, txn["id"])
                                    if t:
                                        session.delete(t)
                                        session.commit()
                                confirm_dialog.close()
                                edit_dialog.close()
                                if on_save_callback:
                                    on_save_callback()
                            ui.button(_("Delete"), on_click=do_delete, color="red")
                            ui.button(_("Cancel"), on_click=confirm_dialog.close).props("flat")
                    confirm_dialog.open()
                ui.button(_("Delete"), on_click=delete, color="red").props("flat")

        with ui.row():
            def save():
                acc_id = account_options.get(account_select.value)
                method_id = method_options.get(method_select.value)
                target_id = account_options.get(target_select.value) if internal_check.value else None

                with session_factory() as session:
                    if is_new:
                        session.add(RecurringTransaction(
                            name=name_input.value,
                            payee=payee_input.value,
                            description=desc_input.value,
                            amount=amount_input.value,
                            is_estimate=estimate_check.value,
                            day_of_month=int(day_input.value),
                            months_active=months_input.value,
                            payment_method_id=method_id,
                            account_id=acc_id,
                            is_internal=internal_check.value,
                            target_account_id=target_id,
                            start_year=int(start_year_input.value),
                            start_month=int(start_month_input.value),
                            end_year=int(end_year_input.value) if has_end.value else None,
                            end_month=int(end_month_input.value) if has_end.value else None,
                        ))
                    else:
                        existing = session.get(RecurringTransaction, txn["id"])
                        existing.name = name_input.value
                        existing.payee = payee_input.value
                        existing.description = desc_input.value
                        existing.amount = amount_input.value
                        existing.is_estimate = estimate_check.value
                        existing.day_of_month = int(day_input.value)
                        existing.months_active = months_input.value
                        existing.payment_method_id = method_id
                        existing.account_id = acc_id
                        existing.is_internal = internal_check.value
                        existing.target_account_id = target_id
                        existing.start_year = int(start_year_input.value)
                        existing.start_month = int(start_month_input.value)
                        existing.end_year = int(end_year_input.value) if has_end.value else None
                        existing.end_month = int(end_month_input.value) if has_end.value else None
                    session.commit()

                edit_dialog.close()
                if on_save_callback:
                    on_save_callback()

            ui.button(_("Save"), on_click=save)
            ui.button(_("Cancel"), on_click=edit_dialog.close).props("flat")

    edit_dialog.open()


def open_transactions_dialog(session_factory, on_save_callback=None) -> None:
    """Open a dialog for managing recurring transactions."""

    def refresh_list():
        txn_list.clear()
        with session_factory() as session:
            txns = (
                session.query(RecurringTransaction)
                .order_by(RecurringTransaction.name)
                .all()
            )
            txn_data = []
            for t in txns:
                txn_data.append({
                    "id": t.id,
                    "name": t.name,
                    "payee": t.payee,
                    "description": t.description,
                    "amount": float(t.amount),
                    "is_estimate": t.is_estimate,
                    "day_of_month": t.day_of_month,
                    "months_active": t.months_active,
                    "payment_method_id": t.payment_method_id,
                    "payment_method_name": t.payment_method.name,
                    "account_id": t.account_id,
                    "account_name": t.account.name,
                    "is_internal": t.is_internal,
                    "target_account_id": t.target_account_id,
                    "target_account_name": t.target_account.name if t.target_account else None,
                    "start_year": t.start_year,
                    "start_month": t.start_month,
                    "end_year": t.end_year,
                    "end_month": t.end_month,
                    "deactivated": t.deactivated_at is not None,
                })

            # Sort: injections first, then bills; within each group by payee, then name
            txn_data.sort(key=lambda t: (
                0 if t["amount"] > 0 else 1,
                t["payee"] or "",
                t["name"],
            ))

        with txn_list:
            if not txn_data:
                ui.label(_("No transactions yet."))
                return

            # Show injections first, then bills
            for txn in txn_data:
                if not show_inactive_check.value and txn["deactivated"]:
                    continue

                is_inj = txn["amount"] > 0
                color = "#e8f5e9" if is_inj else "#ffebee"
                opacity = "opacity: 0.5;" if txn["deactivated"] else ""
                type_label = _("Injection") if is_inj else _("Bill")

                def make_on_save(t=txn):
                    def cb():
                        refresh_list()
                        if on_save_callback:
                            on_save_callback()
                    return cb

                with ui.card().style(f"width: 100%; padding: 8px; margin-bottom: 4px; background: {color}; {opacity}"):
                    with ui.row().style("align-items: center; width: 100%; flex-wrap: nowrap; gap: 8px;"):
                        ui.label(f"{txn['payee']} - {txn['name']}").style("font-weight: bold; width: 220px; min-width: 220px; max-width: 220px; word-wrap: break-word;")
                        ui.label(f"{txn['amount']:,.0f}").style("width: 90px; min-width: 90px; max-width: 90px; text-align: right;")
                        ui.label(f"{type_label}").style("width: 70px; min-width: 70px; max-width: 70px; font-size: 12px;")
                        ui.label(f"{txn['account_name']}").style("width: 110px; min-width: 110px; max-width: 110px; font-size: 12px; word-wrap: break-word;")
                        ui.label(f"{txn['payment_method_name']}").style("width: 110px; min-width: 110px; max-width: 110px; font-size: 12px; word-wrap: break-word;")
                        est = _("Est.") if txn["is_estimate"] else _("Fixed")
                        ui.label(est).style("width: 40px; min-width: 40px; max-width: 40px; font-size: 12px;")
                        if txn["deactivated"]:
                            ui.badge(_("Inactive"), color="grey")
                        ui.space()
                        ui.button(icon="edit", on_click=lambda t=txn: open_transaction_edit(
                            session_factory, t, on_save_callback=make_on_save(t)
                        )).props("flat dense")

    with ui.dialog() as dialog, ui.card().style("min-width: 900px; max-height: 80vh;"):
        with ui.row().style("align-items: center; width: 100%;"):
            ui.label(_("Recurring Transactions")).style("font-size: 20px; font-weight: bold; flex: 1;")
            show_inactive_check = ui.checkbox(_("Show inactive"), value=False, on_change=lambda: refresh_list())
            ui.button(_("New Transaction"), on_click=lambda: open_transaction_edit(
                session_factory, on_save_callback=lambda: (refresh_list(), on_save_callback() if on_save_callback else None)
            ))

        txn_list = ui.column().style("width: 100%; overflow-y: auto;")
        refresh_list()

        ui.button(_("Close"), on_click=dialog.close).props("flat")

    dialog.open()
