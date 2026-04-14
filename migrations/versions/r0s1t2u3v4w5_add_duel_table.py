"""add duel table for Octogroin

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-04-14 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'r0s1t2u3v4w5'
down_revision = 'q9r0s1t2u3v4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'duel',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='waiting'),
        sa.Column('visibility', sa.String(length=20), nullable=False, server_default='public'),
        sa.Column('stake', sa.Float(), nullable=False, server_default='0'),

        sa.Column('player1_id', sa.Integer(), nullable=False),
        sa.Column('pig1_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=True),
        sa.Column('pig2_id', sa.Integer(), nullable=True),
        sa.Column('challenged_user_id', sa.Integer(), nullable=True),

        sa.Column('current_round', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pig1_position', sa.Float(), nullable=False, server_default='0'),
        sa.Column('pig2_position', sa.Float(), nullable=False, server_default='0'),
        sa.Column('pig1_endurance', sa.Float(), nullable=False, server_default='100'),
        sa.Column('pig2_endurance', sa.Float(), nullable=False, server_default='100'),
        sa.Column('arena_type', sa.String(length=30), nullable=False, server_default='classic'),

        sa.Column('round_actions_p1', sa.Text(), nullable=True),
        sa.Column('round_actions_p2', sa.Text(), nullable=True),
        sa.Column('round_deadline_at', sa.DateTime(), nullable=True),

        sa.Column('replay_json', sa.Text(), nullable=True),
        sa.Column('winner_id', sa.Integer(), nullable=True),

        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['player1_id'], ['user.id'], name='fk_duel_player1'),
        sa.ForeignKeyConstraint(['pig1_id'], ['pig.id'], name='fk_duel_pig1'),
        sa.ForeignKeyConstraint(['player2_id'], ['user.id'], name='fk_duel_player2'),
        sa.ForeignKeyConstraint(['pig2_id'], ['pig.id'], name='fk_duel_pig2'),
        sa.ForeignKeyConstraint(['challenged_user_id'], ['user.id'], name='fk_duel_challenged'),
        sa.ForeignKeyConstraint(['winner_id'], ['user.id'], name='fk_duel_winner'),
    )
    op.create_index('ix_duel_player1_id', 'duel', ['player1_id'])
    op.create_index('ix_duel_pig1_id', 'duel', ['pig1_id'])
    op.create_index('ix_duel_player2_id', 'duel', ['player2_id'])
    op.create_index('ix_duel_pig2_id', 'duel', ['pig2_id'])
    op.create_index('ix_duel_challenged_user_id', 'duel', ['challenged_user_id'])
    op.create_index('ix_duel_winner_id', 'duel', ['winner_id'])
    op.create_index('ix_duel_lobby', 'duel', ['status', 'visibility', 'created_at'])


def downgrade():
    op.drop_index('ix_duel_lobby', table_name='duel')
    op.drop_index('ix_duel_winner_id', table_name='duel')
    op.drop_index('ix_duel_challenged_user_id', table_name='duel')
    op.drop_index('ix_duel_pig2_id', table_name='duel')
    op.drop_index('ix_duel_player2_id', table_name='duel')
    op.drop_index('ix_duel_pig1_id', table_name='duel')
    op.drop_index('ix_duel_player1_id', table_name='duel')
    op.drop_table('duel')
