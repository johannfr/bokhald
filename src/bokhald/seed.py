"""Seed default data into the database."""

from sqlalchemy.orm import Session

from bokhald.models import PaymentMethod


DEFAULT_PAYMENT_METHODS = [
    PaymentMethod(
        name="Krafa",
        description="",
        url=None,
    ),
    PaymentMethod(
        name="Automatic transfer",
        description="",
        url=None,
    ),
    PaymentMethod(
        name="Credit card",
        description="",
        url=None,
    ),
    PaymentMethod(
        name="Paypal",
        description="",
        url="https://www.paypal.com/myaccount/autopay/",
    ),
    PaymentMethod(
        name="Google Play",
        description="",
        url="https://play.google.com/store/account/subscriptions",
    ),
]


def seed_payment_methods(session: Session) -> None:
    """Seed default payment methods if none exist."""
    existing = session.query(PaymentMethod).count()
    if existing == 0:
        for pm in DEFAULT_PAYMENT_METHODS:
            session.add(PaymentMethod(name=pm.name, description=pm.description, url=pm.url))
        session.commit()
