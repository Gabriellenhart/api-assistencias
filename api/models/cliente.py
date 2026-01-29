from .base import db
from datetime import datetime

class Cliente(db.Model):
    __tablename__ = 'clientes'
    
    id_cliente = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    # Adicionando outros campos que seus formulários usam
    contato_nome = db.Column(db.String(255))
    contato_email = db.Column(db.String(255))
    contato_telefone = db.Column(db.String(50))
    
    # Integração SolarZ
    documento = db.Column(db.String(50)) # CPF/CNPJ
    ativo = db.Column(db.Boolean, default=True)
    solarz_id = db.Column(db.BigInteger, unique=True, index=True)
    solarz_uuid = db.Column(db.String(64), unique=True, index=True)
    solarz_last_sync_at = db.Column(db.DateTime)
    solarz_payload = db.Column(db.Text)  # JSON completo
    solarz_payload_updated_at = db.Column(db.DateTime)
    ultimo_acesso = db.Column(db.DateTime) # Último acesso na plataforma SolarZ
    
    # Enriquecimento de Dados (Planilha ODS)
    dados_planilha = db.Column(db.JSON) # PostgreSQL JSONB
    
    # Relacionamentos
    usinas = db.relationship('Usina', back_populates='cliente', lazy='select')
    chamados = db.relationship('Chamado', back_populates='cliente')
    orcamentos = db.relationship('Orcamento', back_populates='cliente')

class Usina(db.Model):
    __tablename__ = 'usinas'
    
    id_usina = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    nome_usina = db.Column(db.String(255), nullable=False)
    uc = db.Column(db.String(50)) # Unidade Consumidora (Chave Natural)
    
    # Campos de Endereço/Mapa
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))
    logradouro = db.Column(db.String(255))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    cep = db.Column(db.String(20))
    pais = db.Column(db.String(50))
    
    # Integração SolarZ
    cliente_id_solarz = db.Column(db.BigInteger, index=True) # Vínculo direto SolarZ 1:N
    solarz_id = db.Column(db.BigInteger, unique=True, index=True)
    solarz_uuid = db.Column(db.String(64), unique=True, index=True)
    solarz_last_sync_at = db.Column(db.DateTime)
    solarz_payload = db.Column(db.Text)  # JSON completo
    solarz_payload_updated_at = db.Column(db.DateTime)
    tags = db.Column(db.Text) # Tags convertidas para string (ex: "Tag1, Tag2")
    
    # Enriquecimento de Dados
    dados_planilha = db.Column(db.JSON)
    
    # Relacionamentos
    cliente = db.relationship('Cliente', back_populates='usinas')
    chamados = db.relationship('Chamado', back_populates='usina')
    orcamentos = db.relationship('Orcamento', back_populates='usina')