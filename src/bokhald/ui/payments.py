"""Payment method management UI."""

from __future__ import annotations

from gettext import gettext as _

from nicegui import ui

from bokhald.models import PaymentMethod


def open_payments_dialog(session_factory) -> None:
    """Open a dialog for managing payment methods."""

    def refresh_list():
        payment_list.clear()
        with session_factory() as session:
            methods = session.query(PaymentMethod).order_by(PaymentMethod.name).all()
            method_data = [
                {"id": m.id, "name": m.name, "description": m.description, "url": m.url}
                for m in methods
            ]

        with payment_list:
            if not method_data:
                ui.label(_("No payment methods."))
                return

            for pm in method_data:
                with ui.card().style("width: 100%; padding: 8px; margin-bottom: 4px;"):
                    with ui.row().style("align-items: center; width: 100%;"):
                        ui.label(pm["name"]).style("font-weight: bold; flex: 1;")
                        if pm["url"]:
                            ui.link("URL", pm["url"], new_tab=True)
                        ui.button(icon="edit", on_click=lambda p=pm: open_edit(p)).props("flat dense")

    def open_edit(pm: dict | None = None) -> None:
        is_new = pm is None

        with ui.dialog() as edit_dialog, ui.card().style("min-width: 400px;"):
            ui.label(_("New Payment Method") if is_new else _("Edit Payment Method")).style(
                "font-size: 18px; font-weight: bold;"
            )

            name_input = ui.input(label=_("Name"), value="" if is_new else pm["name"])
            desc_input = ui.textarea(label=_("Description"), value="" if is_new else pm["description"])
            url_input = ui.input(label=_("URL (optional)"), value="" if is_new else (pm["url"] or ""))

            with ui.row():
                def save():
                    with session_factory() as session:
                        if is_new:
                            session.add(PaymentMethod(
                                name=name_input.value,
                                description=desc_input.value,
                                url=url_input.value or None,
                            ))
                        else:
                            existing = session.get(PaymentMethod, pm["id"])
                            existing.name = name_input.value
                            existing.description = desc_input.value
                            existing.url = url_input.value or None
                        session.commit()
                    edit_dialog.close()
                    refresh_list()

                ui.button(_("Save"), on_click=save)
                ui.button(_("Cancel"), on_click=edit_dialog.close).props("flat")

        edit_dialog.open()

    with ui.dialog() as dialog, ui.card().style("min-width: 500px; max-height: 80vh;"):
        with ui.row().style("align-items: center; width: 100%;"):
            ui.label(_("Payment Methods")).style("font-size: 20px; font-weight: bold; flex: 1;")
            ui.button(_("New Payment Method"), on_click=lambda: open_edit())

        payment_list = ui.column().style("width: 100%;")
        refresh_list()

        ui.button(_("Close"), on_click=dialog.close).props("flat")

    dialog.open()
