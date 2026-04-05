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
    # Utilisation de IF NOT EXISTS (PostgreSQL) pour rendre la migration idempotente
    # au cas où certaines colonnes existeraient déjà en base.
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS haras_listed BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS haras_price FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS haras_services_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_vitesse FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_endurance FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_agilite FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_force FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_intelligence FLOAT")
    op.execute("ALTER TABLE pig ADD COLUMN IF NOT EXISTS gene_moral FLOAT")


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
