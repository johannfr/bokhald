"""add amount_changes table

Revision ID: a3f1c8d92e4a
Revises: 9119de706bcb
Create Date: 2026-05-07 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c8d92e4a'
down_revision: Union[str, None] = '9119de706bcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'amount_changes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recurring_transaction_id', sa.Integer(), nullable=False),
        sa.Column('effective_year', sa.Integer(), nullable=False),
        sa.Column('effective_month', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['recurring_transaction_id'], ['recurring_transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recurring_transaction_id', 'effective_year', 'effective_month', name='uq_amount_change_per_month'),
    )


def downgrade() -> None:
    op.drop_table('amount_changes')
