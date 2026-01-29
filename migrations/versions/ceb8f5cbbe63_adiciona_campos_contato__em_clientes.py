"""Adiciona campos contato_* em clientes e cria tabela categorias

Revision ID: ceb8f5cbbe63
Revises: 2b0aec9cab50
Create Date: 2025-11-15 15:45:24.713905
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "ceb8f5cbbe63"
down_revision = "2b0aec9cab50"
branch_labels = None
depends_on = None


def upgrade():
    # Cria tabela de categorias (seu código já tem model Categoria)
    op.create_table(
        "categorias",
        sa.Column("id_categoria", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id_categoria"),
        sa.UniqueConstraint("nome"),
    )

    # Adiciona campos de contato em clientes
    with op.batch_alter_table("clientes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("contato_nome", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("contato_email", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("contato_telefone", sa.String(length=50), nullable=True)
        )
        # IMPORTANTE: NÃO remover a coluna telefone aqui para não perder dados
        # Se um dia quiser migrar telefone -> contato_telefone, faz isso em uma migration de dados.


def downgrade():
    # Remove os campos de contato em clientes
    with op.batch_alter_table("clientes", schema=None) as batch_op:
        batch_op.drop_column("contato_telefone")
        batch_op.drop_column("contato_email")
        batch_op.drop_column("contato_nome")

    # Remove tabela categorias
    op.drop_table("categorias")
