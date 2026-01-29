from .. import db
from datetime import datetime

class SystemUpdate(db.Model):
    __tablename__ = 'system_updates'

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False) # v1.0.0
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False) # Markdown content
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # FK para quem postou
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    usuario = db.relationship('Usuario', backref=db.backref('system_updates', lazy=True))

    def __repr__(self):
        return f'<SystemUpdate {self.version}>'
