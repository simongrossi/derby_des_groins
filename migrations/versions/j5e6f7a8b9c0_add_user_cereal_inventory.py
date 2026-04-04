"""add user cereal inventory

Revision ID: j5e6f7a8b9c0
Revises: i4d5e6f7a8b9
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j5e6f7a8b9c0'
down_revision = 'i4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_cereal_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cereal_key', sa.String(length=30), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'cereal_key', name='uq_user_cereal'),
    )
    op.create_index(
        op.f('ix_user_cereal_inventory_user_id'),
        'user_cereal_inventory',
        ['user_id'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_user_cereal_inventory_user_id'), table_name='user_cereal_inventory')
    op.drop_table('user_cereal_inventory')
