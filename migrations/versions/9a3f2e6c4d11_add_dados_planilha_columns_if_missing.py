"""Ensure dados_planilha columns exist in clientes and usinas

Revision ID: 9a3f2e6c4d11
Revises: 7f41b92d8649
Create Date: 2026-03-01 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9a3f2e6c4d11"
down_revision = "7f41b92d8649"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name, column_name):
    if not _has_table(inspector, table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "clientes") and not _has_column(inspector, "clientes", "dados_planilha"):
        with op.batch_alter_table("clientes", schema=None) as batch_op:
            batch_op.add_column(sa.Column("dados_planilha", sa.JSON(), nullable=True))

    if _has_table(inspector, "usinas") and not _has_column(inspector, "usinas", "dados_planilha"):
        with op.batch_alter_table("usinas", schema=None) as batch_op:
            batch_op.add_column(sa.Column("dados_planilha", sa.JSON(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "usinas", "dados_planilha"):
        with op.batch_alter_table("usinas", schema=None) as batch_op:
            batch_op.drop_column("dados_planilha")

    if _has_column(inspector, "clientes", "dados_planilha"):
        with op.batch_alter_table("clientes", schema=None) as batch_op:
            batch_op.drop_column("dados_planilha")
