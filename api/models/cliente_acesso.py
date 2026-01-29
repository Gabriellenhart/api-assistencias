from .base import db
from datetime import datetime

class ClienteAcessoSolarz(db.Model):
    __tablename__ = 'clientes_acessos_solarz'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id_solarz = db.Column(db.BigInteger, nullable=False, index=True) # Referencia o ID SolarZ (não a PK local)
    data_ref = db.Column(db.Date, nullable=False, index=True)
    ultimo_acesso_detectado = db.Column(db.DateTime)
    qtd_acessos_estimados = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Nota: Em teoria cliente_id_solarz deveria ser FK para clientes.solarz_id
    # Mas como solarz_id em clientes é unique, poderíamos mapear relacionamento.
    # Porém, para manter simples e desacoplado, deixaremos como valor solto por enquanto
    # ou podemos mapear se necessário para joins no ORM.
