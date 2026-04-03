"""add hangman word item

Revision ID: b1c2d3e4f5a6
Revises: dba87ebffc9d
Create Date: 2026-04-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'dba87ebffc9d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hangman_word_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('word', sa.String(length=40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('word'),
    )
    hangman_word_item = sa.table(
        'hangman_word_item',
        sa.column('word', sa.String(length=40)),
        sa.column('is_active', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
    )
    op.bulk_insert(
        hangman_word_item,
        [
            {'word': 'PURIN', 'is_active': True, 'sort_order': 0},
            {'word': 'TRUFFES', 'is_active': True, 'sort_order': 1},
            {'word': 'TIRELIRE', 'is_active': True, 'sort_order': 2},
            {'word': 'JAMBON', 'is_active': True, 'sort_order': 3},
            {'word': 'VETERINAIRE', 'is_active': True, 'sort_order': 4},
            {'word': 'AVOINE', 'is_active': True, 'sort_order': 5},
            {'word': 'COTE', 'is_active': True, 'sort_order': 6},
            {'word': 'PELOTON', 'is_active': True, 'sort_order': 7},
            {'word': 'SAUCISSON', 'is_active': True, 'sort_order': 8},
            {'word': 'ENDURANCE', 'is_active': True, 'sort_order': 9},
            {'word': 'PARIS', 'is_active': True, 'sort_order': 10},
            {'word': 'FERMIER', 'is_active': True, 'sort_order': 11},
            {'word': 'PRAIRIE', 'is_active': True, 'sort_order': 12},
        ],
    )


def downgrade():
    op.drop_table('hangman_word_item')
