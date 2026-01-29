# /run.py

import os
from api import create_app, db

# Cria a aplicação usando a factory
app = create_app(os.getenv('FLASK_ENV') or 'default')

@app.shell_context_processor
def make_shell_context():
    """
    Permite acesso fácil ao app e db no shell interativo do Flask.
    Ex: `flask shell`
    """
    # Importe seus modelos aqui para que fiquem disponíveis no shell
    from api.models.usuario import Usuario
    return {'app': app, 'db': db, 'Usuario': Usuario}

if __name__ == '__main__':
    app.run()