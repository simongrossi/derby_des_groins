"""add pendu daily counter

Revision ID: f1a2b3c4d5e6
Revises: c4d5e6f7a8b9
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('pendu_plays_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('last_pendu_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'last_pendu_at')
    op.drop_column('user', 'pendu_plays_today')
