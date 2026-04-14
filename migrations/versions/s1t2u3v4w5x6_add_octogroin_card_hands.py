"""add octogroin card hand columns

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-04-14 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 's1t2u3v4w5x6'
down_revision = 'r0s1t2u3v4w5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('duel') as batch:
        batch.add_column(sa.Column('hand_p1_json', sa.Text(), nullable=True))
        batch.add_column(sa.Column('hand_p2_json', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('duel') as batch:
        batch.drop_column('hand_p2_json')
        batch.drop_column('hand_p1_json')
