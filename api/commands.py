# /api/commands.py

import click
from flask.cli import with_appcontext
from . import db
#from .models import Usuario
from .models import Usuario, db

@click.command(name='create-admin')
@with_appcontext
def create_admin():
    """Cria um novo usuário administrativo no banco de dados."""
    
    nome = click.prompt('Digite o nome do administrador', type=str)
    email = click.prompt('Digite o e-mail do administrador', type=str)
    
    # Verifica se o e-mail já existe
    if Usuario.query.filter_by(email=email).first():
        click.echo(click.style(f"Erro: O e-mail '{email}' já está em uso.", fg='red'))
        return

    password = click.prompt('Digite a senha', hide_input=True, confirmation_prompt=True)
    
    admin = Usuario(
        nome_usuario=nome,
        email=email,
        nivel='admin'
    )
    admin.password = password # Usa o setter que criamos

    try:
        db.session.add(admin)
        db.session.commit()
        click.echo(click.style(f"Administrador '{nome}' criado com sucesso!", fg='green'))
    except Exception as e:
        db.session.rollback()
        click.echo(click.style(f"Erro ao criar administrador: {e}", fg='red'))

@click.command(name='reset-password')
@with_appcontext
def reset_password():
    """Altera a senha de um usuário existente."""
    
    email = click.prompt('Digite o e-mail do usuário cuja senha deseja alterar', type=str)
    
    # Busca o usuário pelo e-mail
    user = Usuario.query.filter_by(email=email).first()
    
    if not user:
        click.echo(click.style(f"Erro: Usuário com e-mail '{email}' não encontrado.", fg='red'))
        return

    # Pede a nova senha com confirmação
    new_password = click.prompt('Digite a nova senha', hide_input=True, confirmation_prompt=True)
    
    # Valida o comprimento da nova senha
    if len(new_password) < 8:
        click.echo(click.style(f"Erro: A nova senha deve ter no mínimo 8 caracteres.", fg='red'))
        return
        
    # Define a nova senha usando o setter (que faz o hashing)
    user.password = new_password

    try:
        db.session.commit()
        click.echo(click.style(f"Senha do usuário '{user.nome_usuario}' ({email}) alterada com sucesso!", fg='green'))
    except Exception as e:
        db.session.rollback()
        click.echo(click.style(f"Erro ao alterar a senha: {e}", fg='red'))