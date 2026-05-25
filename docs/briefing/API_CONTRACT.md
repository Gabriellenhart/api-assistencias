# Contrato de API — Briefing Operacional Diário

## 1. Endpoint

```http
GET /briefing/diario
````

---

## 2. Autenticação

Este endpoint requer autenticação JWT.

Enviar o token no header:

```http
Authorization: Bearer <access_token>
```

Sem token válido, o backend retorna o erro padrão de autenticação do Flask-JWT-Extended.

---

## 3. Base URL em desenvolvimento

Ambiente local:

```text
http://localhost:5000
```

Exemplo completo:

```http
GET http://localhost:5000/briefing/diario
```

---

## 4. Query parameters

| Parâmetro        |    Tipo | Obrigatório |     Padrão | Limite | Descrição                                               |
| ---------------- | ------: | ----------: | ---------: | -----: | ------------------------------------------------------- |
| `escopo`         |  string |         não | `chamados` |      - | No MVP, somente `chamados` é suportado.                 |
| `data`           |  string |         não | data atual |      - | Data de referência no formato `YYYY-MM-DD`.             |
| `responsavel_id` | integer |         não |       null |      - | Filtra por responsável quando o campo existir no model. |
| `limite`         | integer |         não |       `50` |  `200` | Quantidade máxima de tarefas retornadas.                |

---

## 5. Exemplos de requisição

### 5.1. Briefing padrão

```http
GET /briefing/diario
Authorization: Bearer <access_token>
```

### 5.2. Limitar a 10 tarefas

```http
GET /briefing/diario?limite=10
Authorization: Bearer <access_token>
```

### 5.3. Usar data de referência

```http
GET /briefing/diario?data=2026-05-24
Authorization: Bearer <access_token>
```

### 5.4. Escopo explícito

```http
GET /briefing/diario?escopo=chamados
Authorization: Bearer <access_token>
```

### 5.5. Escopo inválido

```http
GET /briefing/diario?escopo=orcamentos
Authorization: Bearer <access_token>
```

Retorna erro `400`, porque orçamentos ainda não fazem parte do MVP.

---

## 6. Resposta 200 — Sucesso

```json
{
  "data_referencia": "2026-05-24",
  "gerado_em": "2026-05-23T18:15:00",
  "escopo": "chamados",
  "resumo": {
    "total": 18,
    "criticos": 3,
    "altos": 6,
    "medios": 7,
    "baixos": 2,
    "atrasados": 5,
    "vencem_hoje": 2,
    "vencem_amanha": 4,
    "sem_prazo": 6,
    "sem_responsavel": 2,
    "sem_atualizacao": 5,
    "aguardando_cliente": 4
  },
  "tarefas": [
    {
      "ordem": 1,
      "tipo": "chamado",
      "id": 123,
      "codigo": "CH-123",
      "titulo": "Inversor sem comunicação",
      "cliente": "Cliente Exemplo",
      "usina": "Usina Exemplo",
      "status": "em andamento",
      "status_operacional": "sem_prazo",
      "prioridade_original": "alta",
      "prioridade": "alta",
      "prazo": null,
      "prazo_label": "Sem prazo",
      "status_prazo": "sem_prazo",
      "ultima_acao": "Status atual: em andamento.",
      "proxima_acao": "Definir prazo e próxima etapa do atendimento.",
      "motivo": "sem prazo, sem atualização recente",
      "motivos": [
        "sem prazo",
        "sem atualização recente"
      ],
      "dias_sem_atualizacao": 3,
      "score": 55,
      "url": "/chamados/123"
    }
  ]
}
```

---

## 7. Campos da resposta principal

| Campo             | Tipo   | Descrição                                            |
| ----------------- | ------ | ---------------------------------------------------- |
| `data_referencia` | string | Data usada para cálculo de prazo e atualização.      |
| `gerado_em`       | string | Data/hora em que o briefing foi gerado.              |
| `escopo`          | string | Escopo retornado. No MVP: `chamados`.                |
| `resumo`          | object | Contadores consolidados.                             |
| `tarefas`         | array  | Lista de tarefas operacionais derivadas de chamados. |

---

## 8. Campos de `resumo`

| Campo                | Tipo    | Descrição                                            |
| -------------------- | ------- | ---------------------------------------------------- |
| `total`              | integer | Total de tarefas retornadas.                         |
| `criticos`           | integer | Quantidade com prioridade operacional crítica.       |
| `altos`              | integer | Quantidade com prioridade operacional alta.          |
| `medios`             | integer | Quantidade com prioridade operacional média.         |
| `baixos`             | integer | Quantidade com prioridade operacional baixa.         |
| `atrasados`          | integer | Quantidade com prazo atrasado.                       |
| `vencem_hoje`        | integer | Quantidade com prazo vencendo na data de referência. |
| `vencem_amanha`      | integer | Quantidade com prazo vencendo no dia seguinte.       |
| `sem_prazo`          | integer | Quantidade sem prazo identificado.                   |
| `sem_responsavel`    | integer | Quantidade sem responsável identificado.             |
| `sem_atualizacao`    | integer | Quantidade sem atualização há 2 dias ou mais.        |
| `aguardando_cliente` | integer | Quantidade identificada como aguardando cliente.     |

---

## 9. Campos de `tarefas[]`

| Campo                  | Tipo          | Descrição                                       |
| ---------------------- | ------------- | ----------------------------------------------- |
| `ordem`                | integer       | Ordem sugerida de execução.                     |
| `tipo`                 | string        | Tipo da origem. No MVP: `chamado`.              |
| `id`                   | integer/null  | ID do chamado.                                  |
| `codigo`               | string        | Código visual do chamado, exemplo `CH-123`.     |
| `titulo`               | string        | Título resumido do chamado.                     |
| `cliente`              | string        | Nome do cliente ou fallback.                    |
| `usina`                | string        | Nome da usina ou fallback.                      |
| `status`               | string        | Status original do chamado.                     |
| `status_operacional`   | string        | Status operacional calculado.                   |
| `prioridade_original`  | string        | Prioridade original normalizada.                |
| `prioridade`           | string        | Prioridade operacional calculada pelo briefing. |
| `prazo`                | string/null   | Prazo em formato ISO date ou null.              |
| `prazo_label`          | string        | Texto curto do prazo.                           |
| `status_prazo`         | string        | Classificação do prazo.                         |
| `ultima_acao`          | string        | Última ação resumida.                           |
| `proxima_acao`         | string        | Próxima ação sugerida.                          |
| `motivo`               | string        | Motivos concatenados em texto curto.            |
| `motivos`              | array[string] | Lista de motivos operacionais.                  |
| `dias_sem_atualizacao` | integer       | Dias desde a última atualização identificada.   |
| `score`                | integer       | Score operacional entre 0 e 100.                |
| `url`                  | string        | URL relativa para abrir o chamado no frontend.  |

---

## 10. Valores possíveis

### 10.1. `status_prazo`

```text
sem_prazo
atrasado
vence_hoje
vence_amanha
futuro
```

### 10.2. `prioridade`

```text
critica
alta
media
baixa
```

### 10.3. `tipo`

```text
chamado
```

---

## 11. Respostas de erro

### 11.1. Escopo inválido

Status:

```http
400 Bad Request
```

Resposta:

```json
{
  "erro": "Escopo ainda não suportado no MVP."
}
```

---

### 11.2. Data inválida

Status:

```http
400 Bad Request
```

Resposta:

```json
{
  "erro": "Parâmetro data inválido. Use o formato YYYY-MM-DD."
}
```

---

### 11.3. Responsável inválido

Status:

```http
400 Bad Request
```

Resposta:

```json
{
  "erro": "Parâmetro responsavel_id inválido."
}
```

---

### 11.4. Limite inválido

Status:

```http
400 Bad Request
```

Resposta:

```json
{
  "erro": "Parâmetro limite inválido."
}
```

---

### 11.5. Token ausente ou inválido

Status esperado:

```http
401 Unauthorized
```

ou:

```http
422 Unprocessable Entity
```

O retorno segue o padrão do Flask-JWT-Extended configurado no projeto.

---

### 11.6. Erro inesperado

Status:

```http
500 Internal Server Error
```

Resposta:

```json
{
  "erro": "Erro ao gerar briefing diário."
}
```

---

## 12. Regras para o frontend

O frontend deve consumir preferencialmente:

```text
resumo
tarefas
```

O frontend não precisa recalcular:

```text
score
prioridade
status_prazo
proxima_acao
motivos
```

Esses dados já vêm prontos do backend.

---

## 13. Sugestão de layout no frontend

### Cards de resumo

Usar o objeto `resumo` para cards:

```text
Total
Críticos
Altos
Atrasados
Vencem hoje
Sem prazo
Sem responsável
Sem atualização
```

### Lista principal

Usar `tarefas[]` para tabela ou cards com:

```text
ordem
codigo
cliente
usina
titulo
prioridade
prazo_label
ultima_acao
proxima_acao
motivos
```

### Ação de abrir chamado

Usar o campo:

```text
url
```

Exemplo:

```text
/chamados/123
```

---

## 14. Observação

Este contrato representa o MVP atual.
Futuras versões poderão adicionar novos escopos como:

```text
orcamentos
ordens_servico
garantias
```

````

Salve.

---

# Etapa 4 — Atualizar `README.md`

Agora vamos só adicionar links. Não precisa escrever muita coisa.

Abra:

```bash
nano README.md
````

No final do arquivo, adicione:

```md
## Documentação do Briefing Operacional

- [Briefing Operacional Diário — MVP](docs/briefing/BRIEFING_MVP.md)
- [Contrato de API — Briefing Operacional](docs/briefing/API_CONTRACT.md)
```

Se já existir uma seção de documentação, coloque os links nela.

---

# Etapa 5 — Rodar validação

Rode:

```bash
python -m pytest
python -m compileall api scraper scripts config.py run.py
```

Resultado esperado:

```text
26 passed, 2 skipped
compileall sem erro
```

Ou mais testes, dependendo do estado atual do projeto.

---

# Etapa 6 — Conferir arquivos alterados

```bash
git status
```

Você deve ver algo como:

```text
modified: README.md
new file: docs/briefing/BRIEFING_MVP.md
new file: docs/briefing/API_CONTRACT.md
```

Não deve aparecer:

```text
.env
backups
database.dump
uploads
logs
```

Se aparecer algum arquivo de upload/cache, não adicione.

---

# Etapa 7 — Commit

```bash
git add docs/briefing/BRIEFING_MVP.md docs/briefing/API_CONTRACT.md README.md

git commit -m "docs: document briefing MVP and API contract"

git push
```

---

# Resumo desta fase

Nesta fase você vai criar:

```text
docs/briefing/BRIEFING_MVP.md
```

Para documentar:

```text
o que é o módulo
como funciona
quais regras usa
quais limitações tem
quais próximas fases existem
```

E vai criar:

```text
docs/briefing/API_CONTRACT.md
```

Para documentar:

```text
endpoint
autenticação
query params
respostas
erros
campos retornados
orientação para o frontend
```

Depois disso, o backend fica com o MVP documentado e pronto para a próxima etapa: **integração no frontend**.
