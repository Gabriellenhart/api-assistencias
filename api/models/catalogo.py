# /api/models/catalogo.py (VERSÃO CORRIGIDA E COMPLETA)

from .base import db # <-- Importa de .base
from sqlalchemy.sql import func

class Material(db.Model):
    __tablename__ = 'materiais'
    id_material = db.Column(db.Integer, primary_key=True)
    nome_material = db.Column(db.String(255), nullable=False, unique=True)
    valor_venda = db.Column(db.Numeric(10, 2), nullable=False)
    
class Servico(db.Model):
    __tablename__ = 'servicos'
    id_servico = db.Column(db.Integer, primary_key=True)
    nome_servico = db.Column(db.String(255), nullable=False, unique=True)
    valor_servico = db.Column(db.Numeric(10, 2), nullable=False)

class Categoria(db.Model):
    __tablename__ = 'categorias'
    
    id_categoria = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    tipo = db.Column(db.String(50), nullable=False, default='categoria_chamado')
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Categoria {self.nome}>'

class Parametro(db.Model):
    __tablename__ = 'parametros'
    
    id_parametro = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False) # JSON stringified para compatibilidade ampla ou texto simples
    tipo = db.Column(db.String(20), default='string') # string, json, float, int, boolean
    descricao = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<Parametro {self.chave}: {self.valor}>'

class Modalidade(db.Model):
    __tablename__ = 'modalidades'
    
    id_modalidade = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False) # ex: assistencia_paga
    nome = db.Column(db.String(100), nullable=False)
    icone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)
    configuracao = db.Column(db.Text) # JSON stringified contendo preços e regras
    
    def __repr__(self):
        return f'<Modalidade {self.nome}>'