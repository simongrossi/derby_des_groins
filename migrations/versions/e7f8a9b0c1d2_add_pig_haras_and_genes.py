"""add pig haras and genes

Revision ID: e7f8a9b0c1d2
Revises: f1a2b3c4d5e6
Create Date: 2026-04-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Haras Porcin — marketplace P2P
    op.add_column('pig', sa.Column('haras_listed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('pig', sa.Column('haras_price', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('haras_services_count', sa.Integer(), nullable=False, server_default='0'))

    # ADN — potentiel génétique héréditaire (0-100, nullable sur anciens cochons)
    op.add_column('pig', sa.Column('gene_vitesse', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('gene_endurance', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('gene_agilite', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('gene_force', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('gene_intelligence', sa.Float(), nullable=True))
    op.add_column('pig', sa.Column('gene_moral', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('pig', 'gene_moral')
    op.drop_column('pig', 'gene_intelligence')
    op.drop_column('pig', 'gene_force')
    op.drop_column('pig', 'gene_agilite')
    op.drop_column('pig', 'gene_endurance')
    op.drop_column('pig', 'gene_vitesse')
    op.drop_column('pig', 'haras_services_count')
    op.drop_column('pig', 'haras_price')
    op.drop_column('pig', 'haras_listed')
