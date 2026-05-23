# API Assistencias

Backend Flask/PostgreSQL para gerenciamento de chamados e assistencias. O modulo de chamados/assistencias e o nucleo mais estavel usado em producao; outros modulos seguem em desenvolvimento ou refatoracao incremental.

## Stack principal

- Python 3.8+
- Flask, Flask-SQLAlchemy, Flask-Migrate/Alembic
- PostgreSQL
- JWT para autenticacao
- Marshmallow para validacao/serializacao
- Pytest para testes

## Ambiente de desenvolvimento local

### Requisitos

- Python 3.10+ recomendado.
- PostgreSQL local acessivel.
- Cliente PostgreSQL (`psql`, `createdb`, `dropdb`) para bootstrap/reset no Linux/WSL.
- Git e Bash no Linux/WSL. No Windows, PowerShell 5+ ou PowerShell 7.

### Clonar e configurar

```bash
git clone <url-do-repositorio>
cd api-assistencias
./scripts/dev/bootstrap.sh
```

O bootstrap cria `.venv`, instala `requirements.txt`, cria `.env` a partir de `.env.example` se necessario, valida a conexao PostgreSQL configurada em `DEV_DATABASE_URI`, roda migrations e executa `scripts/dev/check.sh`.

No Windows PowerShell:

```powershell
git clone <url-do-repositorio>
cd api-assistencias
.\scripts\dev\bootstrap.ps1
```

A versao PowerShell instala dependencias e roda validacoes basicas. Confirme o PostgreSQL local e rode migrations manualmente se necessario:

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
```

### Variaveis de ambiente

1. Copie `.env.example` para `.env`.
2. Ajuste `SECRET_KEY`, `JWT_SECRET_KEY`, `DEV_DATABASE_URI` e, em producao, `DATABASE_URI`.
3. Configure `CORS_ORIGINS` com origens separadas por virgula. Em desenvolvimento, use por exemplo `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000`.
4. Configure integracoes, como SolarZ, apenas via variaveis de ambiente.

Uploads reais, logs, backups, dumps, bancos locais e `.env` nao devem ser versionados. O repositorio mantem apenas placeholders como `api/static/uploads/.gitkeep` e `storage/.gitkeep`.

Exemplo local:

```bash
DEV_DATABASE_URI=postgresql://assistencias:assistencias@localhost:5432/assistencias_dev
TEST_DATABASE_URI=postgresql://assistencias:assistencias@localhost:5432/assistencias_test
```

### Rodar a API

Linux/WSL:

```bash
./scripts/dev/run.sh
```

Windows PowerShell:

```powershell
.\scripts\dev\run.ps1
```

Por padrao a API sobe em `http://127.0.0.1:5000`.

### Validar o projeto

```bash
./scripts/dev/check.sh
```

No Windows:

```powershell
.\scripts\dev\check.ps1
```

O check importa a app, roda `compileall`, executa `pytest` quando disponivel e tenta consultar `flask db current`.

### Resetar banco local

Use somente em desenvolvimento. O script bloqueia `FLASK_ENV=production` e URIs que parecem producao.

```bash
./scripts/dev/reset_db.sh
```

O reset pede confirmacao digitando `RESET`, apaga e recria o banco de `DEV_DATABASE_URI`, roda migrations e orienta a criacao de admin.

### Admin inicial

Depois das migrations, crie um admin de forma interativa:

```bash
source .venv/bin/activate
python -m flask --app run.py create-admin
```

### Problemas comuns

- `psql nao encontrado`: instale o cliente PostgreSQL.
- `Nao foi possivel conectar ao banco`: revise `DEV_DATABASE_URI` e confirme que o banco existe.
- `flask db current` falha no check: normalmente indica PostgreSQL indisponivel ou `.env` incorreto.
- Scripts sem permissao no Linux/WSL: rode `chmod +x scripts/dev/*.sh`.

Antes de criar ou alterar migrations, revise o impacto em producao e evite alterar migrations ja aplicadas.

## Baseline para GitHub

Esta baseline prioriza seguranca minima e limpeza de versionamento: `.env`, uploads reais, logs, backups, dumps e bancos locais ficam ignorados; secrets sao obrigatorios em producao; CORS e integracoes devem ser configurados por ambiente. Mais detalhes em `docs/releases/GITHUB_BASELINE_PREP.md`.

-----

/sistema-assistencia-api/
|
├── api/                             # Pacote principal da aplicação (o "coração" da API)
│   │
│   ├── __init__.py                  # Application Factory: cria e configura a instância do app Flask
│   │
│   ├── auth/                        # Módulo de autenticação e autorização
│   │   ├── __init__.py
│   │   └── routes.py                # Rotas de login (/auth/login), refresh_token, etc.
│   │
│   ├── models/                      # Módulo para as classes de modelo do SQLAlchemy
│   │   ├── __init__.py
│   │   ├── orcamento.py             # Modelos: Orcamento, OrcamentoMaterial, OrcamentoServico
│   │   ├── chamado.py               # Modelo: Chamado
│   │   ├── usuario.py               # Modelo: Usuario (com métodos para hash de senha)
│   │   └── base.py                  # Modelos base: Cliente, Usina, Material, Servico, etc.
│   │
│   ├── resources/                   # Onde ficam os Endpoints/Blueprints da API (as "rotas")
│   │   ├── __init__.py
│   │   ├── orcamentos.py            # Lógica do endpoint /orcamentos (GET, POST, PUT, DELETE)
│   │   ├── chamados.py              # Lógica do endpoint /chamados
│   │   └── usuarios.py              # Lógica do endpoint /usuarios
│   │
│   ├── schemas/                     # Módulo para os schemas de validação/serialização (Marshmallow)
│   │   ├── __init__.py
│   │   ├── orcamento_schema.py      # Schemas para validação de entrada e formatação de saída de orçamentos
│   │   ├── chamado_schema.py        # Schemas para chamados
│   │   └── usuario_schema.py        # Schemas para usuários
│   │
│   └── services/                    # Lógica de negócio que não pertence a um modelo ou rota
│       ├── __init__.py
│       └── geolocation_service.py   # Função para calcular distância e custo de deslocamento
│
├── migrations/                      # Pasta gerada pelo Flask-Migrate (Alembic) para versionar o DB
│
├── tests/                           # Testes unitários e de integração
│   ├── __init__.py
│   ├── test_orcamentos.py           # Testes específicos para o endpoint de orçamentos
│   └── test_auth.py                 # Testes para o fluxo de autenticação
│
├── .env                             # Arquivo para variáveis de ambiente (NÃO versionar no Git!)
├── .env.example                     # Exemplo de como o .env deve ser (versionar no Git)
├── .gitignore                       # Arquivos e pastas a serem ignorados pelo Git
├── config.py                        # Classes de configuração (Development, Production, Testing)
├── requirements.txt                 # Lista de dependências Python do projeto
├── run.py                           # Ponto de entrada para executar a aplicação em modo de desenvolvimento
└── README.md                        # Documentação do projeto




-----

# **Documentação da API - Sistema de Gerenciamento de Assistências**

**Versão:** 1.0.0
**Última Atualização:** 12 de outubro de 2025
**URL Base:** `http://127.0.0.1:5000`

## **Informações Gerais**

### Autenticação

Todas as rotas, exceto `/auth/login`, requerem autenticação via JSON Web Token (JWT). O token deve ser enviado no cabeçalho `Authorization` com o prefixo `Bearer`.

**Exemplo de Cabeçalho:**
`Authorization: Bearer <seu_access_token>`

### Níveis de Acesso

  * **Técnico:** Pode gerenciar chamados, orçamentos e ordens de serviço. Pode visualizar dados de catálogos e clientes.
  * **Admin:** Possui acesso total, incluindo o gerenciamento de usuários, clientes e catálogos.

### Respostas Padrão

  * **Sucesso:** Códigos `200 OK`, `201 Created`, `204 No Content`.
  * **Erro do Cliente:** `400 Bad Request` (dados de validação inválidos), `401 Unauthorized` (token ausente ou inválido), `403 Forbidden` (nível de acesso insuficiente), `404 Not Found` (recurso não encontrado), `409 Conflict` (recurso já existe, ex: e-mail duplicado).
  * **Erro do Servidor:** `500 Internal Server Error`.

### Paginação

Endpoints de listagem (`GET /recurso`) aceitam os seguintes parâmetros de query:

  * `limit` (int, padrão: 10): Número de resultados por página.
  * `offset` (int, padrão: 0): Número de resultados a pular.

-----

## **1. Autenticação (`/auth`)**

### **POST** `/auth/login`

Autentica um usuário e retorna tokens de acesso e de atualização.

  * **Autorização:** Nenhuma.
  * **Corpo da Requisição (JSON):**
    ```json
    {
        "email": "admin@email.com",
        "password": "sua_senha_segura"
    }
    ```
  * **Resposta de Sucesso (200 OK):**
    ```json
    {
        "message": "Login realizado com sucesso!",
        "access_token": "eyJ...",
        "refresh_token": "eyJ..."
    }
    ```

### **POST** `/auth/refresh`

Gera um novo `access_token` a partir de um `refresh_token` válido.

  * **Autorização:** Requer um **Refresh Token** válido.
  * **Resposta de Sucesso (200 OK):**
    ```json
    {
        "access_token": "eyJ_novo_token_..."
    }
    ```

-----

## **2. Usuários (`/usuarios`)**

  * **Autorização:** Acesso restrito a **Admin**.

| Método | Endpoint                | Descrição                                         |
| :----- | :---------------------- | :------------------------------------------------ |
| `POST` | `/usuarios`             | Cria um novo usuário (técnico ou admin).          |
| `GET`  | `/usuarios`             | Lista todos os usuários do sistema.               |
| `GET`  | `/usuarios/{id_usuario}` | Obtém os detalhes de um usuário específico.       |
| `PUT`  | `/usuarios/{id_usuario}` | Atualiza os dados de um usuário (nome, email, nível, senha). |
| `DELETE` | `/usuarios/{id_usuario}` | Remove um usuário do sistema.                     |

  * **Exemplo de Corpo (POST/PUT):**
    ```json
    {
        "nome_usuario": "Novo Tecnico",
        "email": "tecnico.novo@email.com",
        "password": "senha_forte_123",
        "nivel": "tecnico"
    }
    ```
  * **Exemplo de Resposta (GET):**
    ```json
    {
        "id_usuario": 3,
        "nome_usuario": "Novo Tecnico",
        "email": "tecnico.novo@email.com",
        "nivel": "tecnico"
    }
    ```

-----

## **3. Clientes e Usinas (`/clientes`)**

| Método | Endpoint                   | Descrição                                 | Autorização     |
| :----- | :------------------------- | :---------------------------------------- | :-------------- |
| `POST` | `/clientes`                | Cria um novo cliente.                     | **Admin** |
| `GET`  | `/clientes`                | Lista todos os clientes.                  | Técnico / Admin |
| `GET`  | `/clientes/{id_cliente}`   | Detalha um cliente e lista suas usinas.   | Técnico / Admin |
| `PUT`  | `/clientes/{id_cliente}`   | Atualiza os dados de um cliente.          | **Admin** |
| `DELETE` | `/clientes/{id_cliente}`   | Remove um cliente.                        | **Admin** |
| `POST` | `/{id_cliente}/usinas`     | Cria uma nova usina para um cliente.      | **Admin** |

  * **Exemplo de Corpo (POST `/clientes`):**
    ```json
    {
        "nome": "Cliente Exemplo SA",
        "telefone": "(41) 99999-8888"
    }
    ```
  * **Exemplo de Corpo (POST `/{id_cliente}/usinas`):**
    ```json
    {
        "nome_usina": "Usina de Teste",
        "cidade": "Curitiba",
        "latitude": "-25.4284",
        "longitude": "-49.2733"
    }
    ```

-----

## **4. Catálogos (`/materiais`, `/servicos`, `/inversores`)**

Os endpoints para Materiais, Serviços e Inversores seguem o mesmo padrão CRUD.

| Método | Endpoint     | Descrição                | Autorização     |
| :----- | :----------- | :----------------------- | :-------------- |
| `POST` | `/recurso`   | Cria um novo item.       | **Admin** |
| `GET`  | `/recurso`   | Lista todos os itens.    | Técnico / Admin |
| `GET`  | `/recurso/{id}` | Detalha um item.         | Técnico / Admin |
| `PUT`  | `/recurso/{id}` | Atualiza um item.        | **Admin** |
| `DELETE` | `/recurso/{id}` | Remove um item.          | **Admin** |

  * **Exemplo de Corpo (POST `/materiais`):**
    ```json
    {
        "nome_material": "Painel Solar 600W",
        "unidades": "unidade",
        "valor_custo": "1000.00",
        "valor_venda": "1450.50"
    }
    ```

-----

## **5. Chamados (`/chamados`)**

| Método | Endpoint             | Descrição                                  | Autorização     |
| :----- | :------------------- | :----------------------------------------- | :-------------- |
| `POST` | `/chamados`          | Cria um novo chamado para um cliente.      | Técnico / Admin |
| `GET`  | `/chamados`          | Lista todos os chamados.                   | Técnico / Admin |
| `GET`  | `/chamados/{id_chamado}` | Detalha um chamado específico.             | Técnico / Admin |
| `PUT`  | `/chamados/{id_chamado}` | Atualiza os dados de um chamado.           | Técnico / Admin |
| `DELETE` | `/chamados/{id_chamado}` | Remove um chamado.                         | **Admin** |

  * **Exemplo de Corpo (POST):**
    ```json
    {
        "id_cliente": 1,
        "id_usina": 1,
        "titulo": "Inversor X não está reportando dados",
        "descricao": "O inversor do setor leste parou de comunicar às 14h. Necessário verificar.",
        "categoria": "Falha de Equipamento",
        "prioridade": "Alta"
    }
    ```

-----

## **6. Orçamentos (`/orcamentos`)**

| Método | Endpoint               | Descrição                                            | Autorização     |
| :----- | :--------------------- | :--------------------------------------------------- | :-------------- |
| `POST` | `/orcamentos`          | Cria um novo orçamento.                              | Técnico / Admin |
| `GET`  | `/orcamentos`          | Lista todos os orçamentos.                           | Técnico / Admin |
| `GET`  | `/orcamentos/{id_orcamento}` | Detalha um orçamento, seus itens e cálculos.         | Técnico / Admin |
| `PUT`  | `/orcamentos/{id_orcamento}` | Atualiza um orçamento (itens, status, etc.).       | Técnico / Admin |
| `DELETE` | `/orcamentos/{id_orcamento}` | Remove um orçamento.                                 | **Admin** |

  * **Exemplo de Corpo (POST):**
    ```json
    {
        "id_cliente": 1,
        "id_usina": 1,
        "id_chamado": 1,
        "descricao_servico": "Diagnóstico e possível troca do inversor do setor leste.",
        "desconto": "50.00",
        "data_validade": "2025-10-22T23:59:59-03:00",
        "materiais": [
            { "id": 2, "quantidade": 1 }
        ],
        "servicos": [
            { "id": 1, "quantidade": 1 },
            { "id": 3, "quantidade": 1 }
        ]
    }
    ```
  * **Resposta de Sucesso (201 Created):** Veja o exemplo detalhado na especificação inicial.

-----

## **7. Ordens de Serviço (`/ordens-servico`)**

| Método | Endpoint                    | Descrição                               | Autorização     |
| :----- | :-------------------------- | :-------------------------------------- | :-------------- |
| `POST` | `/ordens-servico`           | Cria uma OS a partir de um orçamento **aprovado**. | Técnico / Admin |
| `GET`  | `/ordens-servico`           | Lista todas as Ordens de Serviço.         | Técnico / Admin |
| `GET`  | `/ordens-servico/{id_os}`   | Detalha uma OS específica.              | Técnico / Admin |
| `PUT`  | `/ordens-servico/{id_os}`   | Atualiza uma OS (status, relatório).    | Técnico / Admin |
| `DELETE` | `/ordens-servico/{id_os}`   | Remove uma OS.                          | **Admin** |

  * **Exemplo de Corpo (POST):**
    ```json
    {
        "id_chamado_vinculado": 1,
        "id_orcamento_associado": 1,
        "data_agendamento": "2025-10-15T09:00:00-03:00"
    }
    ```
  * **Exemplo de Corpo (PUT para finalizar):**
    ```json
    {
        "status": "Concluída",
        "relatorio_tecnico": "Inversor substituído com sucesso. Equipamento antigo recolhido para análise de garantia. Sistema operando normalmente."
    }
    ```
## Linux/WSL Workflow

Consulte a documentacao em `docs/WSL_QUICKSTART.md` para bootstrap e execucao no WSL.

Documentos de governanca de release/migracao:
- `docs/PROD_MIGRATION_PHASES.md`
- `docs/RELEASE_CHECKLIST.md`
