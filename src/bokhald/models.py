"""SQLAlchemy ORM models for Bokhald."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bokhald.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    initial_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    safety_margin: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    transactions: Mapped[list["RecurringTransaction"]] = relationship(
        "RecurringTransaction",
        back_populates="account",
        foreign_keys="RecurringTransaction.account_id",
    )
    incoming_transfers: Mapped[list["RecurringTransaction"]] = relationship(
        "RecurringTransaction",
        back_populates="target_account",
        foreign_keys="RecurringTransaction.target_account_id",
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}')>"


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    transactions: Mapped[list["RecurringTransaction"]] = relationship(
        "RecurringTransaction", back_populates="payment_method"
    )

    def __repr__(self) -> str:
        return f"<PaymentMethod(id={self.id}, name='{self.name}')>"


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payee: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    months_active: Mapped[str] = mapped_column(String(50), nullable=False, default="1-12")
    payment_method_id: Mapped[int] = mapped_column(Integer, ForeignKey("payment_methods.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="transactions", foreign_keys=[account_id]
    )
    target_account: Mapped["Account | None"] = relationship(
        "Account", back_populates="incoming_transfers", foreign_keys=[target_account_id]
    )
    payment_method: Mapped["PaymentMethod"] = relationship(
        "PaymentMethod", back_populates="transactions"
    )
    actual_amounts: Mapped[list["ActualAmount"]] = relationship(
        "ActualAmount", back_populates="recurring_transaction", cascade="all, delete-orphan"
    )
    amount_changes: Mapped[list["AmountChange"]] = relationship(
        "AmountChange", back_populates="recurring_transaction", cascade="all, delete-orphan",
        order_by="AmountChange.effective_year, AmountChange.effective_month",
    )

    @property
    def is_injection(self) -> bool:
        """Return True if this is an injection (positive amount)."""
        return self.amount > 0

    def __repr__(self) -> str:
        return f"<RecurringTransaction(id={self.id}, name='{self.name}', amount={self.amount})>"


class ActualAmount(Base):
    __tablename__ = "actual_amounts"
    __table_args__ = (
        UniqueConstraint("recurring_transaction_id", "year", "month", name="uq_actual_per_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recurring_transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recurring_transactions.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    entered_from_account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True
    )

    # Relationships
    recurring_transaction: Mapped["RecurringTransaction"] = relationship(
        "RecurringTransaction", back_populates="actual_amounts"
    )
    entered_from_account: Mapped["Account | None"] = relationship(
        "Account", foreign_keys=[entered_from_account_id]
    )

    def __repr__(self) -> str:
        return f"<ActualAmount(txn_id={self.recurring_transaction_id}, {self.year}/{self.month}, amount={self.actual_amount})>"


class AmountChange(Base):
    __tablename__ = "amount_changes"
    __table_args__ = (
        UniqueConstraint("recurring_transaction_id", "effective_year", "effective_month", name="uq_amount_change_per_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recurring_transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recurring_transactions.id"), nullable=False
    )
    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    recurring_transaction: Mapped["RecurringTransaction"] = relationship(
        "RecurringTransaction", back_populates="amount_changes"
    )

    def __repr__(self) -> str:
        return f"<AmountChange(txn_id={self.recurring_transaction_id}, from={self.effective_year}/{self.effective_month}, amount={self.amount})>"
