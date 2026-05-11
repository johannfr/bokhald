"""add is_one_time to recurring_transactions

Revision ID: c5f3a7b28d1e
Revises: b4e2f9a01c3d
Create Date: 2026-05-11 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f3a7b28d1e'
down_revision: Union[str, None] = 'b4e2f9a01c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recurring_transactions', sa.Column('is_one_time', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    with op.batch_alter_table('recurring_transactions') as batch_op:
        batch_op.alter_column('is_one_time', server_default=None)


def downgrade() -> None:
    op.drop_column('recurring_transactions', 'is_one_time')
