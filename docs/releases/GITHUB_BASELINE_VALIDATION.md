# Validacao da baseline GitHub

## Data

2026-05-23

## Ambiente Python

- Python: 3.10.11
- Pip: 25.3
- Ambiente virtual local: nao havia `.venv` ativo no momento da validacao.
- Arquivo usado para dependencias: `requirements.txt`.
- `pyproject.toml` existe e configura principalmente metadados do projeto e pytest.

Comandos recomendados para ambiente virtual:

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Linux/WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Comandos executados

```powershell
python --version
pip --version
pip install -r requirements.txt
python -c "from api import create_app; app = create_app('development'); print(app.name)"
python -c "from api import create_app; create_app('production')"
python -m compileall api scraper scripts config.py run.py
python -m pytest
git status --short
```

## Instalacao de dependencias

`pip install -r requirements.txt` concluiu com sucesso.

Observacao: como nao havia virtualenv ativo, o pip instalou no site-packages do usuario e reportou conflitos com pacotes globais nao relacionados ao projeto. Para o primeiro commit e proximas validacoes, recomenda-se repetir em `.venv` limpo.

Nao foi necessario alterar `requirements.txt`; dependencias usadas pela app, incluindo `Flask-Bcrypt`, ja estavam listadas.

## Importacao da aplicacao

Importacao em desenvolvimento validada com variaveis fake/locais:

```powershell
$env:FLASK_ENV='development'
$env:SECRET_KEY='dev-secret'
$env:JWT_SECRET_KEY='dev-jwt-secret'
$env:DEV_DATABASE_URI='postgresql://usuario:senha@localhost:5432/assistencias_dev'
$env:CORS_ORIGINS='http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000'
python -c "from api import create_app; app = create_app('development'); print(app.name)"
```

Resultado: sucesso, app criada com nome `api`.

## Configuracao de producao

Validado que a aplicacao falha em producao quando variaveis obrigatorias estao ausentes. Sem `SECRET_KEY`, `JWT_SECRET_KEY` e `DATABASE_URI`, a importacao falhou com erro claro iniciando por `SECRET_KEY deve ser definida no ambiente de producao`.

Validado que producao aceita variaveis fake/locais quando todas estao definidas.

## CORS

Validado:

- desenvolvimento aceita origens locais comuns via `CORS_ORIGINS`;
- producao rejeita `CORS_ORIGINS='*'`;
- producao aceita lista separada por virgula, por exemplo `https://app.example.com,https://admin.example.com`.

## Compileall

`python -m compileall api scraper scripts config.py run.py` concluiu com sucesso.

## Testes

`python -m pytest` concluiu com:

- 7 passed
- 6 skipped

Os skips parecem relacionados a cenarios que dependem de ambiente externo ou banco de dados preparado.

## Problemas encontrados

- Nao havia `.venv` local ativo; a instalacao foi feita no ambiente de usuario.
- Pip reportou conflitos com pacotes globais externos ao projeto por causa da instalacao fora de virtualenv.
- A validacao de producao sem variaveis obrigatorias falha no primeiro segredo ausente encontrado, o que e suficiente para bloquear execucao insegura.
- `compileall` e `pytest` geram caches locais; eles foram removidos apos a validacao.

## Pendencias antes de deploy em producao

- Criar `.env` real no servidor com `FLASK_ENV=production`.
- Definir `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URI` e `CORS_ORIGINS` reais.
- Garantir PostgreSQL acessivel e migrations revisadas antes de aplicar.
- Validar permissao e persistencia de `UPLOAD_FOLDER`.
- Validar scripts de backup/restore em ambiente controlado.

## Recomendacao

A baseline esta validada o suficiente para um primeiro commit seguro, desde que o commit inclua somente arquivos intencionais e nao inclua `.env`, caches, dumps, logs, backups, bancos locais ou uploads reais.
