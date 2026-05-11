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

    actual_lookup: dict[tuple[int, int, int], tuple[float, int | None]] = {}
    for a in actuals:
        actual_lookup[(a.recurring_transaction_id, a.year, a.month)] = (
            float(a.actual_amount),
            a.entered_from_account_id,
        )

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
            is_incoming = txn in incoming_txns

            if actual_key in actual_lookup:
                raw_amount, entered_from = actual_lookup[actual_key]
                is_actual = True

                if txn.is_internal:
                    entered_from_target = (entered_from == account.id) if is_incoming else (entered_from is not None and entered_from != account.id)
                    if is_incoming:
                        # Viewing from target account side
                        if entered_from_target:
                            # Entered from this (target) side — use as-is
                            amount = raw_amount
                        else:
                            # Entered from source side — flip sign
                            amount = abs(raw_amount)
                    else:
                        # Viewing from source account side
                        if entered_from_target:
                            # Entered from target side — flip sign
                            amount = -abs(raw_amount)
                        else:
                            # Entered from source side — use as-is
                            amount = raw_amount
                else:
                    amount = raw_amount
            else:
                # For internal transfers: if this is an incoming transfer,
                # the amount is the inverse (positive for the target account)
                if is_incoming:
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

    # Find current month index — the injection only applies from now onward
    today = date.today()
    current_idx = 0
    for i, md in enumerate(projection):
        if (md.year, md.month) >= (today.year, today.month):
            current_idx = i
            break

    future = projection[current_idx:]
    if not future:
        return 0.0

    # For a month k steps into the future (0-indexed), changing the injection
    # by X per month shifts its balance by (k+1)*X (since the injection is
    # applied in months 0..k). We need b[k] + (k+1)*X >= safety_margin, so
    # X >= (safety_margin - b[k]) / (k+1). Take the max across all months.
    required = max(
        (safety_margin - md.balance) / (k + 1)
        for k, md in enumerate(future)
    )

    return round(required, 2)
