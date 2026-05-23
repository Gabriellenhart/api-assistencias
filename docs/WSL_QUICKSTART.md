# WSL Quickstart

## Objetivo
Executar o backend DEV com comportamento Linux-first, equivalente ao deploy na VPS.

## Passos
1. Abra Ubuntu no WSL2.
2. Clone/copie este repositório para o filesystem Linux (exemplo: `~/dev/api-assistencias`).
3. Execute:

```bash
chmod +x scripts/*.sh run_scheduler.sh
scripts/dev_wsl_bootstrap.sh
```

4. Suba a API:

```bash
scripts/dev_run_api.sh
```

5. Rode os testes em PostgreSQL:

```bash
export TEST_DATABASE_URI=postgresql://assistencias_test:assistencias_test@localhost:5432/assistencias_test
scripts/dev_test_pipeline.sh
```

6. Agende o scheduler (cron):

```bash
crontab -e
# exemplo: a cada hora
0 * * * * /home/<usuario>/dev/api-assistencias/run_scheduler.sh
```

## Observações
- `run_scheduler.bat` foi mantido apenas como fallback de desenvolvimento em Windows.
- O fluxo padrão de desenvolvimento deve ser WSL.
