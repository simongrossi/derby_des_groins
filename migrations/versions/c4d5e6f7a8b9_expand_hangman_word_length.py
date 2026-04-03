"""expand hangman word length

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-04-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'hangman_word_item',
        'word',
        existing_type=sa.String(length=40),
        type_=sa.String(length=80),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        'hangman_word_item',
        'word',
        existing_type=sa.String(length=80),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
