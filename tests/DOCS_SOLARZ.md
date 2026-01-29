# Documentação da Integração SolarZ

Este documento resume a implementação da sincronização de dados entre a plataforma SolarZ e o backend `api_assistências`.

## 1. Visão Geral

O módulo de integração tem como objetivo manter a base de dados local (`PostgreSQL`) sincronizada com os dados da SolarZ (Usinas e Clientes). A sincronização é **unidirecional** (SolarZ -> Backend) e foi projetada para ser **conservadora**, preservando edições manuais feitas no sistema local sempre que possível.

## 2. Arquitetura

O sistema opera em três camadas:

1.  **Scrapers (`scraper/`)**: Scripts autônomos responsáveis por autenticar na SolarZ e extrair dados brutos (JSON).
2.  **Service Layer (`api/services/solarz_service.py`)**: Recebe os dados brutos e aplica as regras de *Matching* e *Upsert*.
3.  **Scheduler (`scheduler.py`)**: Orquestrador que executa os scrapers periodicamente.

## 3. Funcionalidades Implementadas

### 3.1. Sincronização de Usinas
*   **Fonte**: API SolarZ (`upsert_usina_solarz`).
*   **Dados Importados**: Nome, Endereço (Cidade, Estado, CEP, Geolocalização), Status (Monitorada/Não Monitorada).
*   **Regra de Vínculo (Matching)**:
    1.  `solarz_uuid` (Match exato e definitivo).
    2.  `solarz_id` (Match por ID numérico).
    3.  **Fallback**: Nome da Usina + (Cidade OU Estado).
*   **Cliente Placeholder**: Se a usina vier sem cliente identificado, ela é vinculada a um cliente padrão "SolarZ - Cliente não informado".

### 3.2. Sincronização de Clientes
*   **Fonte**: API SolarZ (`upsert_cliente_solarz`).
*   **Dados Importados**: Nome, Documento (CPF/CNPJ), Email, Telefone/WhatsApp, Status (Ativo).
*   **Regra de Vínculo**:
    1.  `solarz_uuid`.
    2.  `solarz_id`.
    3.  `documento` (CPF/CNPJ).
*   **Payload Bruto**: O JSON completo recebido da SolarZ é salvo no campo `solarz_payload` para auditoria.

### 3.3. Automação
*   **Frequência**: A cada 1 hora.
*   **Execução**: Via `scheduler.py` (Python Schedule).
*   **Resiliência**: Scripts possuem retentativa automática (Retry) em caso de falhas de rede.

## 4. Como Executar

### Ambiente de Desenvolvimento (Windows)
Execute o arquivo batch na raiz do projeto:
```bash
run_scheduler.bat
```
Isso abrirá um terminal que executará a sincronização imediatamente e depois aguardará 1 hora para a próxima execução.

### Execução Manual (Avulsa)
Para rodar apenas uma sincronização específica manualmente:

**Usinas:**
```bash
python -m api_assistências.scraper.solarz_sync_usinas
```

**Clientes:**
```bash
python -m api_assistências.scraper.solarz_sync_clientes
```

## 5. Estrutura de Banco de Dados

Novas colunas adicionadas às tabelas `usinas` e `clientes`:
*   `solarz_id` (BigInteger, Unique)
*   `solarz_uuid` (String, Unique)
*   `solarz_last_sync_at` (Timestamp)
*   `solarz_payload` (Text - JSON Raw)
*   `documento` (Clientes - VARCHAR)
*   `ativo` (Clientes - Boolean)

---
*Gerado via Assistente AI - 25/12/2025*
