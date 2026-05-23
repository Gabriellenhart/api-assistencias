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
./scripts/dev_wsl_bootstrap.sh
```

O bootstrap:

- valida Python 3.10 no WSL/Linux;
- instala dependencias de sistema quando necessario;
- inicia PostgreSQL local;
- garante os roles `assistencias_dev` e `assistencias_test`;
- garante os bancos `assistencias_dev` e `assistencias_test` com os owners corretos;
- concede `CREATEDB` ao role local `assistencias_test`, usado pelo pytest para bancos temporarios;
- cria `.venv` se necessario;
- instala `requirements.txt`;
- cria `.env` a partir de `.env.example` se ele ainda nao existir e atualiza as URIs locais padrao;
- roda `python -m flask --app run.py db upgrade`;
- roda `python -m flask --app run.py db current`;
- executa uma validacao basica de import e `compileall`.

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
DEV_DATABASE_URI=postgresql://assistencias_dev:assistencias_dev@localhost:5432/assistencias_dev
TEST_DATABASE_URI=postgresql://assistencias_test:assistencias_test@localhost:5432/assistencias_test
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
```

Em producao, defina `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URI` e `CORS_ORIGINS` explicitamente.

## Banco local

Padrao local:

```text
DEV_DB_USER=assistencias_dev
DEV_DB_PASS=assistencias_dev
DEV_DB_NAME=assistencias_dev
TEST_DB_USER=assistencias_test
TEST_DB_PASS=assistencias_test
TEST_DB_NAME=assistencias_test
```

O role `assistencias_test` recebe `CREATEDB` somente no ambiente local para que a fixture do pytest crie bancos temporarios isolados e descarte no teardown.

Se precisar recriar manualmente:

```bash
sudo -u postgres psql -d postgres -c "CREATE ROLE assistencias_dev LOGIN PASSWORD 'assistencias_dev';"
sudo -u postgres psql -d postgres -c "CREATE ROLE assistencias_test LOGIN PASSWORD 'assistencias_test' CREATEDB;"
sudo -u postgres createdb -O assistencias_dev assistencias_dev
sudo -u postgres createdb -O assistencias_test assistencias_test
```

Se o banco existir com owner divergente em ambiente local:

```bash
sudo -u postgres psql -d postgres -c "ALTER DATABASE assistencias_dev OWNER TO assistencias_dev;"
sudo -u postgres psql -d postgres -c "ALTER DATABASE assistencias_test OWNER TO assistencias_test;"
sudo -u postgres psql -d postgres -c "ALTER ROLE assistencias_test CREATEDB;"
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
