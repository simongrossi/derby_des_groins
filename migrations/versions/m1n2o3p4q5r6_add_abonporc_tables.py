"""add abonporc tables

Revision ID: m1n2o3p4q5r6
Revises: l7a8b9c0d1e2
Create Date: 2026-04-07 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'm1n2o3p4q5r6'
down_revision = 'l7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('abonporc_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('status', sa.String(length=20), server_default='lobby', nullable=False),
        sa.Column('phase', sa.String(length=20), server_default='recolte', nullable=True),
        sa.Column('buy_in', sa.Integer(), server_default='0', nullable=False),
        sa.Column('action_seat', sa.Integer(), server_default='1', nullable=True),
        sa.Column('hand_number', sa.Integer(), server_default='0', nullable=True),
        sa.Column('deck_json', sa.Text(), server_default='[]', nullable=True),
        sa.Column('center_pigs_json', sa.Text(), server_default='[]', nullable=True),
        sa.Column('state_json', sa.Text(), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=True),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, nullable=True),
    )
    op.create_table('abonporc_player',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('table_id', sa.Integer(), sa.ForeignKey('abonporc_table.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('seat', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='waiting', nullable=True),
        sa.Column('hand_json', sa.Text(), server_default='[]', nullable=True),
        sa.Column('vehicle_json', sa.Text(), server_default='null', nullable=True),
        sa.Column('trailer_json', sa.Text(), server_default='null', nullable=True),
        sa.Column('gray_card_json', sa.Text(), server_default='null', nullable=True),
        sa.Column('victory_pigs_json', sa.Text(), server_default='[]', nullable=True),
        sa.Column('larcins_json', sa.Text(), server_default='[]', nullable=True),
        sa.Column('vote', sa.Integer(), nullable=True),
        sa.Column('joined_at', sa.DateTime(), default=datetime.utcnow, nullable=True),
        sa.UniqueConstraint('table_id', 'seat', name='uq_abonporc_table_seat')
    )
    op.create_index(op.f('ix_abonporc_player_table_id'), 'abonporc_player', ['table_id'], unique=False)
    op.create_index(op.f('ix_abonporc_player_user_id'), 'abonporc_player', ['user_id'], unique=False)


def downgrade():
    op.drop_table('abonporc_player')
    op.drop_table('abonporc_table')
