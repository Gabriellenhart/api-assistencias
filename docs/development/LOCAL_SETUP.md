# Ambiente local de desenvolvimento

## Visao geral

Este guia descreve o fluxo recomendado para rodar o backend Flask/PostgreSQL do `api-assistencias` em uma maquina nova. O fluxo canonico fica em `scripts/dev/` e evita alterar rotas, migrations ou scripts de producao.

## Requisitos

- Python 3.10+ recomendado.
- PostgreSQL local.
- Cliente PostgreSQL (`psql`, `createdb`, `dropdb`) no Linux/WSL.
- Git.
- Bash no Linux/WSL ou PowerShell no Windows.

## Instalacao Linux/WSL

```bash
git clone <url-do-repositorio>
cd api-assistencias
./scripts/dev/bootstrap.sh
```

O bootstrap:

- valida que esta em Linux/WSL;
- cria `.venv` se necessario;
- instala `requirements.txt`;
- cria `.env` a partir de `.env.example` se ele ainda nao existir;
- valida conexao com `DEV_DATABASE_URI` ou `DATABASE_URI`;
- roda `python -m flask db upgrade`;
- executa `scripts/dev/check.sh`.

Se o script nao tiver permissao de execucao:

```bash
chmod +x scripts/dev/*.sh
```

## Instalacao Windows

O fluxo PowerShell e mais conservador e nao tenta criar/resetar banco automaticamente.

```powershell
git clone <url-do-repositorio>
cd api-assistencias
.\scripts\dev\bootstrap.ps1
```

Depois de revisar `.env` e garantir PostgreSQL local, rode migrations:

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
```

Para iniciar:

```powershell
.\scripts\dev\run.ps1
```

## Variaveis de ambiente

O projeto carrega `.env` via `python-dotenv`. Use `.env.example` como base e nunca versione `.env`.

Exemplo local:

```env
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=change-me-local-secret
JWT_SECRET_KEY=change-me-local-jwt-secret
DEV_DATABASE_URI=postgresql://assistencias:assistencias@localhost:5432/assistencias_dev
TEST_DATABASE_URI=postgresql://assistencias:assistencias@localhost:5432/assistencias_test
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
```

Em producao, defina `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URI` e `CORS_ORIGINS` explicitamente.

## Banco local

O bootstrap nao imprime senhas e nao sobrescreve `.env`. Se o banco ainda nao existir, crie manualmente com um usuario local sem segredos reais:

```bash
sudo -u postgres createuser --createdb --login assistencias
sudo -u postgres psql -c "ALTER USER assistencias WITH PASSWORD 'assistencias';"
createdb -h localhost -U assistencias assistencias_dev
createdb -h localhost -U assistencias assistencias_test
```

Se sua instalacao PostgreSQL usa outro usuario administrativo, adapte os comandos.

## Migrations

O projeto usa Flask-Migrate/Alembic:

```bash
source .venv/bin/activate
python -m flask --app run.py db upgrade
python -m flask --app run.py db current
```

Nao altere migrations existentes sem revisar impacto em producao.

## Comandos uteis

Iniciar API:

```bash
./scripts/dev/run.sh
```

Validar projeto:

```bash
./scripts/dev/check.sh
```

Resetar banco local:

```bash
./scripts/dev/reset_db.sh
```

Criar admin inicial:

```bash
source .venv/bin/activate
python -m flask --app run.py create-admin
```

Rodar testes diretamente:

```bash
source .venv/bin/activate
python -m pytest
```

## Troubleshooting

- `psql nao encontrado`: instale `postgresql-client` ou pacote equivalente.
- `Nao foi possivel conectar ao banco`: confira host, porta, usuario, senha e nome do banco em `DEV_DATABASE_URI`.
- `flask db upgrade` falha por conexao: o PostgreSQL local nao esta acessivel ou o banco ainda nao existe.
- `pytest` pula testes: alguns cenarios dependem de banco preparado.
- `CORS_ORIGINS='*'` em producao: bloqueado de proposito; configure origens explicitas.
- PowerShell bloqueia script: ajuste a policy apenas para o escopo do usuario, se permitido pela sua maquina.
