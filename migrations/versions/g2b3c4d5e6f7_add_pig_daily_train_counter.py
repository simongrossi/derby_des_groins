"""add pig daily train counter

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pig', sa.Column('daily_train_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pig', sa.Column('last_train_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('pig', 'last_train_date')
    op.drop_column('pig', 'daily_train_count')
