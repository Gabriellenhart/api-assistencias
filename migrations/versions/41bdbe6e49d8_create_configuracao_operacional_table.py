"""create_configuracao_operacional_table

Revision ID: 41bdbe6e49d8
Revises: 13379ed960b3
Create Date: 2026-02-01 15:13:57.057188

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41bdbe6e49d8'
down_revision = '13379ed960b3'
branch_labels = None
depends_on = None


def upgrade():
    # Create configuracao_operacional table
    op.create_table('configuracao_operacional',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('margem_seguranca_minutos', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('velocidade_media_kmh', sa.Numeric(precision=5, scale=2), nullable=False, server_default='50.0'),
        sa.Column('tempo_medio_por_categoria', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feriados', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default configuration
    op.execute("""
        INSERT INTO configuracao_operacional (
            margem_seguranca_minutos, 
            velocidade_media_kmh, 
            tempo_medio_por_categoria,
            feriados
        ) VALUES (
            30,
            50.0,
            '{"Manutenção Preventiva": 90, "Instalação": 180, "Reparo": 120, "Vistoria": 60}'::jsonb,
            '[]'::jsonb
        )
    """)


def downgrade():
    # Drop configuracao_operacional table
    op.drop_table('configuracao_operacional')

