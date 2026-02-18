"""add_operational_fields_to_usuarios

Revision ID: 13379ed960b3
Revises: 8598a38814ec
Create Date: 2026-02-01 15:12:39.089031

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13379ed960b3'
down_revision = '8598a38814ec'
branch_labels = None
depends_on = None


def upgrade():
    # Add operational fields to usuarios table
    op.add_column('usuarios', sa.Column('horario_inicio', sa.Time(), nullable=True, server_default='08:00:00'))
    op.add_column('usuarios', sa.Column('horario_fim', sa.Time(), nullable=True, server_default='18:00:00'))
    op.add_column('usuarios', sa.Column('latitude_base', sa.String(length=50), nullable=True))
    op.add_column('usuarios', sa.Column('longitude_base', sa.String(length=50), nullable=True))


def downgrade():
    # Remove operational fields from usuarios table
    op.drop_column('usuarios', 'longitude_base')
    op.drop_column('usuarios', 'latitude_base')
    op.drop_column('usuarios', 'horario_fim')
    op.drop_column('usuarios', 'horario_inicio')

