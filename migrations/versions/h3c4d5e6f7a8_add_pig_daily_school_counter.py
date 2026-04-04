"""add pig daily school counter

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h3c4d5e6f7a8'
down_revision = 'g2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pig', sa.Column('daily_school_sessions', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pig', sa.Column('last_school_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('pig', 'last_school_date')
    op.drop_column('pig', 'daily_school_sessions')
