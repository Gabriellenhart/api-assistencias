# DocumentaÃ§Ã£o da IntegraÃ§Ã£o SolarZ

Este documento resume a implementaÃ§Ã£o da sincronizaÃ§Ã£o de dados entre a plataforma SolarZ e o backend `api-assistencias`.

## 1. VisÃ£o Geral

O mÃ³dulo de integraÃ§Ã£o tem como objetivo manter a base de dados local (`PostgreSQL`) sincronizada com os dados da SolarZ (Usinas e Clientes). A sincronizaÃ§Ã£o Ã© **unidirecional** (SolarZ -> Backend) e foi projetada para ser **conservadora**, preservando ediÃ§Ãµes manuais feitas no sistema local sempre que possÃ­vel.

## 2. Arquitetura

O sistema opera em trÃªs camadas:

1.  **Scrapers (`scraper/`)**: Scripts autÃ´nomos responsÃ¡veis por autenticar na SolarZ e extrair dados brutos (JSON).
2.  **Service Layer (`api/services/solarz_service.py`)**: Recebe os dados brutos e aplica as regras de *Matching* e *Upsert*.
3.  **Scheduler (`scheduler.py`)**: Orquestrador que executa os scrapers periodicamente.

## 3. Funcionalidades Implementadas

### 3.1. SincronizaÃ§Ã£o de Usinas
*   **Fonte**: API SolarZ (`upsert_usina_solarz`).
*   **Dados Importados**: Nome, EndereÃ§o (Cidade, Estado, CEP, GeolocalizaÃ§Ã£o), Status (Monitorada/NÃ£o Monitorada).
*   **Regra de VÃ­nculo (Matching)**:
    1.  `solarz_uuid` (Match exato e definitivo).
    2.  `solarz_id` (Match por ID numÃ©rico).
    3.  **Fallback**: Nome da Usina + (Cidade OU Estado).
*   **Cliente Placeholder**: Se a usina vier sem cliente identificado, ela Ã© vinculada a um cliente padrÃ£o "SolarZ - Cliente nÃ£o informado".

### 3.2. SincronizaÃ§Ã£o de Clientes
*   **Fonte**: API SolarZ (`upsert_cliente_solarz`).
*   **Dados Importados**: Nome, Documento (CPF/CNPJ), Email, Telefone/WhatsApp, Status (Ativo).
*   **Regra de VÃ­nculo**:
    1.  `solarz_uuid`.
    2.  `solarz_id`.
    3.  `documento` (CPF/CNPJ).
*   **Payload Bruto**: O JSON completo recebido da SolarZ Ã© salvo no campo `solarz_payload` para auditoria.

### 3.3. AutomaÃ§Ã£o
*   **FrequÃªncia**: A cada 1 hora.
*   **ExecuÃ§Ã£o**: Via `scheduler.py` (Python Schedule).
*   **ResiliÃªncia**: Scripts possuem retentativa automÃ¡tica (Retry) em caso de falhas de rede.

## 4. Como Executar

### Ambiente de Desenvolvimento (Windows)
Execute o arquivo batch na raiz do projeto:
```bash
run_scheduler.bat
```
Isso abrirÃ¡ um terminal que executarÃ¡ a sincronizaÃ§Ã£o imediatamente e depois aguardarÃ¡ 1 hora para a prÃ³xima execuÃ§Ã£o.

### ExecuÃ§Ã£o Manual (Avulsa)
Para rodar apenas uma sincronizaÃ§Ã£o especÃ­fica manualmente:

**Usinas:**
```bash
python scraper/solarz_sync_usinas.py
```

**Clientes:**
```bash
python scraper/solarz_sync_clientes.py
```

## 5. Estrutura de Banco de Dados

Novas colunas adicionadas Ã s tabelas `usinas` e `clientes`:
*   `solarz_id` (BigInteger, Unique)
*   `solarz_uuid` (String, Unique)
*   `solarz_last_sync_at` (Timestamp)
*   `solarz_payload` (Text - JSON Raw)
*   `documento` (Clientes - VARCHAR)
*   `ativo` (Clientes - Boolean)

---
*Gerado via Assistente AI - 25/12/2025*

