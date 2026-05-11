"""add entered_from_account_id to actual_amounts

Revision ID: b4e2f9a01c3d
Revises: a3f1c8d92e4a
Create Date: 2026-05-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e2f9a01c3d'
down_revision: Union[str, None] = 'a3f1c8d92e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('actual_amounts')"))]
    if 'entered_from_account_id' not in columns:
        op.add_column(
            'actual_amounts',
            sa.Column('entered_from_account_id', sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            'fk_actual_amounts_entered_from_account',
            'actual_amounts',
            'accounts',
            ['entered_from_account_id'],
            ['id'],
        )


def downgrade() -> None:
    op.drop_constraint('fk_actual_amounts_entered_from_account', 'actual_amounts', type_='foreignkey')
    op.drop_column('actual_amounts', 'entered_from_account_id')
