# Checklist de Release para VPS

## Pré-release
- [ ] Branch/tag da release definida.
- [ ] `pytest` em PostgreSQL concluído com sucesso.
- [ ] Migrations revisadas (upgrade/downgrade).
- [ ] Validação de compatibilidade com frontend.
- [ ] Nenhum artefato local no pacote (`venv`, `logs`, `uploads`, `backups`, `dist_webdock` transitório).

## Deploy
- [ ] Backup de banco executado.
- [ ] Deploy de código na VPS.
- [ ] `flask db upgrade` aplicado.
- [ ] Serviço API reiniciado (`systemd`).
- [ ] Scheduler/cron verificado.

## Pós-release
- [ ] Smoke test de autenticação, chamados, OS, planejamento e integrações.
- [ ] Logs sem erros críticos.
- [ ] Métricas de estabilidade acompanhadas.

## Rollback
- [ ] Procedimento de rollback documentado para código e banco.
- [ ] Ponto de restauração validado.
