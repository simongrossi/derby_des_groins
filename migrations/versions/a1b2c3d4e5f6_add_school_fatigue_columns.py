"""add school fatigue columns

Revision ID: a1b2c3d4e5f6
Revises: dba87ebffc9d
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'dba87ebffc9d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pig', sa.Column('school_lessons_today_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pig', sa.Column('school_lessons_today_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('pig', 'school_lessons_today_date')
    op.drop_column('pig', 'school_lessons_today_count')
