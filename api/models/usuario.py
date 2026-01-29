# /api/models/usuario.py

from .base import db            # usa o db que vem de api.__init__
from .. import bcrypt           # bcrypt vem do pacote api

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    nivel = db.Column(db.String(50), nullable=False, default='tecnico')
    avatar_filename = db.Column(db.String(255), nullable=True)
    theme_preference = db.Column(db.String(10), nullable=True, default='system')

    @property
    def password(self):
        raise AttributeError('A senha não é um atributo legível.')

    @password.setter
    def password(self, password_plaintext):
        self.password_hash = bcrypt.generate_password_hash(password_plaintext).decode('utf-8')

    def check_password(self, password_plaintext):
        return bcrypt.check_password_hash(self.password_hash, password_plaintext)

    def __repr__(self):
        return f"<Usuario {self.email}>"
