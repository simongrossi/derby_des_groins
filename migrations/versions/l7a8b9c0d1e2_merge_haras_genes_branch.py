"""merge haras genes branch with main

Revision ID: l7a8b9c0d1e2
Revises: e7f8a9b0c1d2, k6f7a8b9c0d1
Create Date: 2026-04-06 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l7a8b9c0d1e2'
down_revision = ('e7f8a9b0c1d2', 'k6f7a8b9c0d1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
