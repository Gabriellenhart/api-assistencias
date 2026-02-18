"""add_scheduling_fields_to_chamados

Revision ID: 8598a38814ec
Revises: 05b12b07962d
Create Date: 2026-02-01 15:11:58.803710

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8598a38814ec'
down_revision = '05b12b07962d'
branch_labels = None
depends_on = None


def upgrade():
    # Add scheduling fields to chamados table
    op.add_column('chamados', sa.Column('tempo_estimado_minutos', sa.Integer(), nullable=True, server_default='120'))
    op.add_column('chamados', sa.Column('km_estimado', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade():
    # Remove scheduling fields from chamados table
    op.drop_column('chamados', 'km_estimado')
    op.drop_column('chamados', 'tempo_estimado_minutos')

