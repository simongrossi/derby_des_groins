"""add grain futures and market events

Revision ID: p8q9r0s1t2u3
Revises: i4d5e6f7a8b9
Create Date: 2026-04-08 12:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'p8q9r0s1t2u3'
down_revision = 'i4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'market_position_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cursor_x', sa.Integer(), nullable=False),
        sa.Column('cursor_y', sa.Integer(), nullable=False),
        sa.Column('average_surcharge', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('recorded_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_market_position_history_recorded_at'), 'market_position_history', ['recorded_at'], unique=False)

    op.create_table(
        'grain_future_contract',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cereal_key', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('base_unit_price', sa.Float(), nullable=False),
        sa.Column('locked_unit_price', sa.Float(), nullable=False),
        sa.Column('surcharge_locked', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('feeding_multiplier_locked', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('premium_rate', sa.Float(), nullable=False, server_default='0.10'),
        sa.Column('total_price_paid', sa.Float(), nullable=False),
        sa.Column('delivery_due_at', sa.DateTime(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_grain_future_contract_cereal_key'), 'grain_future_contract', ['cereal_key'], unique=False)
    op.create_index(op.f('ix_grain_future_contract_created_at'), 'grain_future_contract', ['created_at'], unique=False)
    op.create_index(op.f('ix_grain_future_contract_delivered_at'), 'grain_future_contract', ['delivered_at'], unique=False)
    op.create_index(op.f('ix_grain_future_contract_delivery_due_at'), 'grain_future_contract', ['delivery_due_at'], unique=False)
    op.create_index(op.f('ix_grain_future_contract_status'), 'grain_future_contract', ['status'], unique=False)
    op.create_index(op.f('ix_grain_future_contract_user_id'), 'grain_future_contract', ['user_id'], unique=False)

    op.create_table(
        'market_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('blocked_cereal_key', sa.String(length=20), nullable=True),
        sa.Column('cursor_shift_x', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cursor_shift_y', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_market_event_blocked_cereal_key'), 'market_event', ['blocked_cereal_key'], unique=False)
    op.create_index(op.f('ix_market_event_created_at'), 'market_event', ['created_at'], unique=False)
    op.create_index(op.f('ix_market_event_ends_at'), 'market_event', ['ends_at'], unique=False)
    op.create_index(op.f('ix_market_event_event_type'), 'market_event', ['event_type'], unique=False)
    op.create_index(op.f('ix_market_event_starts_at'), 'market_event', ['starts_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_market_event_starts_at'), table_name='market_event')
    op.drop_index(op.f('ix_market_event_event_type'), table_name='market_event')
    op.drop_index(op.f('ix_market_event_ends_at'), table_name='market_event')
    op.drop_index(op.f('ix_market_event_created_at'), table_name='market_event')
    op.drop_index(op.f('ix_market_event_blocked_cereal_key'), table_name='market_event')
    op.drop_table('market_event')

    op.drop_index(op.f('ix_grain_future_contract_user_id'), table_name='grain_future_contract')
    op.drop_index(op.f('ix_grain_future_contract_status'), table_name='grain_future_contract')
    op.drop_index(op.f('ix_grain_future_contract_delivery_due_at'), table_name='grain_future_contract')
    op.drop_index(op.f('ix_grain_future_contract_delivered_at'), table_name='grain_future_contract')
    op.drop_index(op.f('ix_grain_future_contract_created_at'), table_name='grain_future_contract')
    op.drop_index(op.f('ix_grain_future_contract_cereal_key'), table_name='grain_future_contract')
    op.drop_table('grain_future_contract')

    op.drop_index(op.f('ix_market_position_history_recorded_at'), table_name='market_position_history')
    op.drop_table('market_position_history')
