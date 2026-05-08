"""Account management UI."""

from __future__ import annotations

from gettext import gettext as _

from nicegui import ui
from sqlalchemy.orm import Session

from bokhald.models import Account


def open_accounts_dialog(session_factory, on_save_callback=None) -> None:
    """Open a dialog for managing accounts."""

    def refresh_list():
        account_list.clear()
        with session_factory() as session:
            accounts = session.query(Account).order_by(Account.name).all()
            account_data = [
                {"id": a.id, "name": a.name, "initial_balance": float(a.initial_balance),
                 "safety_margin": float(a.safety_margin), "is_default": a.is_default}
                for a in accounts
            ]

        with account_list:
            if not account_data:
                ui.label(_("No accounts yet."))
                return

            for acc in account_data:
                with ui.card().style("width: 100%; padding: 8px; margin-bottom: 4px;"):
                    with ui.row().style("align-items: center; width: 100%;"):
                        default_badge = " *" if acc["is_default"] else ""
                        ui.label(f"{acc['name']}{default_badge}").style("font-weight: bold; flex: 1;")
                        ui.label(f"{_('Balance')}: {acc['initial_balance']:,.0f}")
                        ui.label(f"{_('Margin')}: {acc['safety_margin']:,.0f}")
                        ui.button(icon="edit", on_click=lambda a=acc: open_edit(a)).props("flat dense")

    def open_edit(acc: dict | None = None) -> None:
        """Open edit/create dialog for an account."""
        is_new = acc is None

        with ui.dialog() as edit_dialog, ui.card().style("min-width: 400px;"):
            ui.label(_("New Account") if is_new else _("Edit Account")).style("font-size: 18px; font-weight: bold;")

            name_input = ui.input(label=_("Name"), value="" if is_new else acc["name"])
            balance_input = ui.number(label=_("Initial Balance"), value=0 if is_new else acc["initial_balance"])
            margin_input = ui.number(label=_("Safety Margin"), value=0 if is_new else acc["safety_margin"])
            default_check = ui.checkbox(_("Default account"), value=True if is_new else acc["is_default"])

            with ui.row():
                def save():
                    with session_factory() as session:
                        if default_check.value:
                            # Unset other defaults
                            session.query(Account).filter(Account.is_default == True).update(  # noqa: E712
                                {"is_default": False}
                            )

                        if is_new:
                            # If this is the first account, make it default regardless
                            count = session.query(Account).count()
                            new_acc = Account(
                                name=name_input.value,
                                initial_balance=balance_input.value,
                                safety_margin=margin_input.value,
                                is_default=default_check.value or count == 0,
                            )
                            session.add(new_acc)
                        else:
                            existing = session.get(Account, acc["id"])
                            existing.name = name_input.value
                            existing.initial_balance = balance_input.value
                            existing.safety_margin = margin_input.value
                            existing.is_default = default_check.value

                        session.commit()
                    edit_dialog.close()
                    refresh_list()
                    if on_save_callback:
                        on_save_callback()

                ui.button(_("Save"), on_click=save)
                ui.button(_("Cancel"), on_click=edit_dialog.close).props("flat")

        edit_dialog.open()

    with ui.dialog() as dialog, ui.card().style("min-width: 500px; max-height: 80vh;"):
        with ui.row().style("align-items: center; width: 100%;"):
            ui.label(_("Accounts")).style("font-size: 20px; font-weight: bold; flex: 1;")
            ui.button(_("New Account"), on_click=lambda: open_edit())

        account_list = ui.column().style("width: 100%;")
        refresh_list()

        ui.button(_("Close"), on_click=dialog.close).props("flat")

    dialog.open()
