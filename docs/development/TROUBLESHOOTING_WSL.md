# Troubleshooting WSL

## Migration falha em ix_usinas_cliente_id_solarz

Sintoma:

```bash
python -m flask --app run.py db upgrade
```

Falha com erro semelhante a:

```text
psycopg2.errors.UndefinedColumn: column "cliente_id_solarz" does not exist
CREATE INDEX ix_usinas_cliente_id_solarz ON usinas (cliente_id_solarz)
```

Causa:

A migration `ec668a9bcb9c_add_chamadolembrete_table.py` criava o indice
`ix_usinas_cliente_id_solarz` antes de garantir que a coluna
`usinas.cliente_id_solarz` existisse. Em um banco PostgreSQL limpo, as
migrations anteriores criavam a tabela `usinas`, mas nao criavam essa coluna.

Correcao aplicada:

A migration `ec668a9bcb9c_add_chamadolembrete_table.py` passou a adicionar
`usinas.cliente_id_solarz` como `BigInteger`, nullable, antes de criar o indice
na mesma coluna. O downgrade tambem remove o indice antes da coluna e verifica
a existencia dos objetos antes de tentar altera-los.

Risco:

Esta correcao altera uma migration existente. Em bancos onde
`ec668a9bcb9c` ja foi aplicada, o Alembic nao reaplica automaticamente essa
revision. Antes de qualquer downgrade ou reconciliacao manual em ambientes
persistentes, confirme se a coluna ja existia e se possui dados que precisam ser
preservados.

Como resetar um banco local parcialmente migrado:

```bash
./scripts/dev/reset_db.sh
```

O script mostra o banco alvo e pede a confirmacao `RESET`.

Alternativa manual para desenvolvimento local:

```bash
dropdb assistencias_dev
createdb assistencias_dev -O assistencias_dev
```

Depois rode novamente:

```bash
python -m flask --app run.py db upgrade
python -m flask --app run.py db current
```

## pytest falha ao criar banco temporario

Sintoma:

```text
psycopg2.errors.ActiveSqlTransaction: CREATE DATABASE cannot run inside a transaction block
```

ou:

```text
permission denied to create database
```

Causa:

A fixture de teste cria um banco temporario a partir de `TEST_DATABASE_URI`.
Para isso, a conexao administrativa precisa rodar em autocommit real e o role
local de teste precisa de `CREATEDB`.

Padrao local:

```text
TEST_DATABASE_URI=postgresql://assistencias_test:assistencias_test@localhost:5432/assistencias_test
```

Correcao:

`tests/conftest.py` abre a conexao psycopg2 fora do context manager transacional
e ativa `conn.autocommit = True` antes de executar `CREATE DATABASE` e
`DROP DATABASE`. O bootstrap WSL tambem concede `CREATEDB` ao role
`assistencias_test` apenas no ambiente local.

Para corrigir manualmente:

```bash
sudo -u postgres psql -d postgres -c "ALTER ROLE assistencias_test CREATEDB;"
```

Observacao:

Alguns testes de integracao do scheduling instanciam models completos. Enquanto o
schema migrado local nao contiver todas as colunas desses models, eles sao
marcados como skip com uma mensagem listando as colunas ausentes. Isso evita que
falhas de alinhamento model/migration sejam confundidas com problema de
PostgreSQL, permissao ou bootstrap.

## Owner divergente em assistencias_dev ou assistencias_test

Sintoma:

`scripts/dev/reset_db.sh` pode falhar ao dropar o banco se ele foi criado por
outro role, por exemplo `assistencias`.

Causa:

O padrao atual usa owners separados para desenvolvimento e teste:

```text
assistencias_dev  -> owner de assistencias_dev
assistencias_test -> owner de assistencias_test
```

Correcao local:

```bash
sudo -u postgres psql -d postgres -c "ALTER DATABASE assistencias_dev OWNER TO assistencias_dev;"
sudo -u postgres psql -d postgres -c "ALTER DATABASE assistencias_test OWNER TO assistencias_test;"
```

O bootstrap WSL faz esse ajuste automaticamente quando detecta owners
divergentes em bancos locais.

## Resetar banco dev com seguranca

Use:

```bash
./scripts/dev/reset_db.sh
```

O script bloqueia `FLASK_ENV=production`, rejeita URIs que parecam producao,
exige confirmacao `RESET`, encerra conexoes ativas, recria `assistencias_dev`
com owner `assistencias_dev`, aplica migrations e mostra o revision atual.

Para automacao local controlada:

```bash
./scripts/dev/reset_db.sh --yes
```

O `--yes` ainda exige que a URI aponte para `localhost` e para o banco
`assistencias_dev` com usuario `assistencias_dev`.
