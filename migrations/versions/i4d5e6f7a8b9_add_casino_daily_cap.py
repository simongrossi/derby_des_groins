"""add casino daily cap and daily_casino_wins

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i4d5e6f7a8b9'
down_revision = 'h3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('daily_casino_wins', sa.Float(), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('last_casino_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('user', 'last_casino_date')
    op.drop_column('user', 'daily_casino_wins')
