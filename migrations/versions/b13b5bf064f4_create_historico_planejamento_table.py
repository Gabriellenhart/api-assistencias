"""create_historico_planejamento_table

Revision ID: b13b5bf064f4
Revises: 41bdbe6e49d8
Create Date: 2026-02-01 15:14:28.743252

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b13b5bf064f4'
down_revision = '41bdbe6e49d8'
branch_labels = None
depends_on = None


def upgrade():
    # Create historico_planejamento table
    op.create_table('historico_planejamento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_chamado', sa.Integer(), nullable=False),
        sa.Column('id_usuario_anterior', sa.Integer(), nullable=True),
        sa.Column('id_usuario_novo', sa.Integer(), nullable=True),
        sa.Column('data_agendamento_anterior', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_agendamento_novo', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo', sa.String(length=255), nullable=True),
        sa.Column('usuario_responsavel_mudanca', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['id_chamado'], ['chamados.id_chamado'], ),
        sa.ForeignKeyConstraint(['id_usuario_anterior'], ['usuarios.id_usuario'], ),
        sa.ForeignKeyConstraint(['id_usuario_novo'], ['usuarios.id_usuario'], ),
        sa.ForeignKeyConstraint(['usuario_responsavel_mudanca'], ['usuarios.id_usuario'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop historico_planejamento table
    op.drop_table('historico_planejamento')

