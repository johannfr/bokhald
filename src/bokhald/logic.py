"""Business logic: month parsing, projection engine, injection calculator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from bokhald.models import Account, ActualAmount, AmountChange, RecurringTransaction


def parse_months(pattern: str) -> set[int]:
    """Parse a month pattern string into a set of month numbers.

    Examples:
        "1-12" -> {1,2,3,4,5,6,7,8,9,10,11,12}
        "1-3,7,12" -> {1,2,3,7,12}
        "6" -> {6}
    """
    months: set[int] = set()
    for part in pattern.split(","):
        part = part.strip()
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s.strip()), int(end_s.strip())
            months.update(range(start, end + 1))
        else:
            months.add(int(part))
    return months


@dataclass
class MonthData:
    """Data for a single month in the projection."""
    year: int
    month: int
    amounts: dict[int, float]  # transaction_id -> amount (actual if available, else estimated)
    is_actual: dict[int, bool]  # transaction_id -> whether the amount is actual
    balance: float = 0.0
    recommended_injection: float = 0.0


def _iter_months(start_year: int, start_month: int, end_year: int, end_month: int):
    """Yield (year, month) tuples from start to end inclusive."""
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def is_transaction_active(txn: RecurringTransaction, year: int, month: int) -> bool:
    """Check if a transaction is active for a given year/month."""
    if txn.deactivated_at is not None:
        deact_date = date(txn.deactivated_at.year, txn.deactivated_at.month, 1)
        check_date = date(year, month, 1)
        if check_date >= deact_date:
            return False

    if (year, month) < (txn.start_year, txn.start_month):
        return False

    if txn.end_year is not None and txn.end_month is not None:
        if (year, month) > (txn.end_year, txn.end_month):
            return False

    active_months = parse_months(txn.months_active)
    if month not in active_months:
        return False

    return True


def build_projection(
    session: Session,
    account: Account,
    num_future_months: int = 24,
) -> list[MonthData]:
    """Build a month-by-month projection for an account.

    Returns a list of MonthData from the earliest transaction start date
    to current month + num_future_months.
    """
    # Get all transactions for this account (both owned and incoming internal)
    owned_txns: list[RecurringTransaction] = (
        session.query(RecurringTransaction)
        .filter(RecurringTransaction.account_id == account.id)
        .all()
    )
    incoming_txns: list[RecurringTransaction] = (
        session.query(RecurringTransaction)
        .filter(
            RecurringTransaction.target_account_id == account.id,
            RecurringTransaction.is_internal == True,  # noqa: E712
        )
        .all()
    )

    all_txns = owned_txns + incoming_txns

    if not all_txns:
        # No transactions, return empty projection from current month
        today = date.today()
        return [MonthData(year=today.year, month=today.month, amounts={}, is_actual={})]

    # Determine date range
    start_dates = [(t.start_year, t.start_month) for t in all_txns]
    earliest = min(start_dates)

    today = date.today()
    end_year, end_month = today.year, today.month
    # Add future months
    end_month += num_future_months
    while end_month > 12:
        end_month -= 12
        end_year += 1

    # Build actual amounts lookup
    txn_ids = [t.id for t in all_txns]
    actuals: list[ActualAmount] = (
        session.query(ActualAmount)
        .filter(ActualAmount.recurring_transaction_id.in_(txn_ids))
        .all()
    ) if txn_ids else []

    actual_lookup: dict[tuple[int, int, int], float] = {}
    for a in actuals:
        actual_lookup[(a.recurring_transaction_id, a.year, a.month)] = float(a.actual_amount)

    # Build amount changes lookup: txn_id -> sorted list of (effective_year, effective_month, amount)
    amount_changes: list[AmountChange] = (
        session.query(AmountChange)
        .filter(AmountChange.recurring_transaction_id.in_(txn_ids))
        .order_by(AmountChange.effective_year, AmountChange.effective_month)
        .all()
    ) if txn_ids else []

    change_lookup: dict[int, list[tuple[int, int, float]]] = {}
    for ac in amount_changes:
        change_lookup.setdefault(ac.recurring_transaction_id, []).append(
            (ac.effective_year, ac.effective_month, float(ac.amount))
        )

    def _get_effective_amount(txn_id: int, base_amount: float, year: int, month: int) -> float:
        """Get the effective amount for a transaction at a given month, considering amount changes."""
        changes = change_lookup.get(txn_id)
        if not changes:
            return base_amount
        # Find the latest change on or before (year, month)
        effective = base_amount
        for ey, em, amt in changes:
            if (ey, em) <= (year, month):
                effective = amt
            else:
                break
        return effective

    # Build projection
    projection: list[MonthData] = []
    balance = float(account.initial_balance)

    for year, month in _iter_months(earliest[0], earliest[1], end_year, end_month):
        month_data = MonthData(year=year, month=month, amounts={}, is_actual={})

        for txn in all_txns:
            if not is_transaction_active(txn, year, month):
                continue

            actual_key = (txn.id, year, month)
            if actual_key in actual_lookup:
                amount = actual_lookup[actual_key]
                is_actual = True
            else:
                # For internal transfers: if this is an incoming transfer,
                # the amount is the inverse (positive for the target account)
                if txn in incoming_txns:
                    amount = abs(_get_effective_amount(txn.id, float(txn.amount), year, month))
                else:
                    amount = _get_effective_amount(txn.id, float(txn.amount), year, month)
                is_actual = False

            month_data.amounts[txn.id] = amount
            month_data.is_actual[txn.id] = is_actual

        month_total = sum(month_data.amounts.values())
        balance += month_total
        month_data.balance = balance

        projection.append(month_data)

    return projection


def calculate_recommended_injection(
    session: Session,
    account: Account,
    num_future_months: int = 24,
) -> float:
    """Calculate the minimum monthly injection needed so the balance
    never drops below the safety margin.

    Returns a negative value if current injections exceed what is needed.
    """
    projection = build_projection(session, account, num_future_months)

    if not projection:
        return 0.0

    safety_margin = float(account.safety_margin)

    # Find the worst (lowest) balance across all projected months
    min_balance = min(md.balance for md in projection)

    # Positive = shortfall (need more injection), negative = excess (injecting too much)
    shortfall = safety_margin - min_balance

    # Simple approach: how much per month to cover the shortfall
    # We need to find how many months until the minimum point
    min_month_idx = next(i for i, md in enumerate(projection) if md.balance == min_balance)
    months_until_min = max(min_month_idx, 1)

    return round(shortfall / months_until_min, 2)
