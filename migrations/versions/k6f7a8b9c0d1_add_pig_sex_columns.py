"""add pig sex columns

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k6f7a8b9c0d1'
down_revision = 'j5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pig', sa.Column('sex', sa.String(length=1), nullable=False, server_default='M'))
    op.add_column('auction', sa.Column('pig_sex', sa.String(length=1), nullable=False, server_default='M'))


def downgrade():
    op.drop_column('auction', 'pig_sex')
    op.drop_column('pig', 'sex')
