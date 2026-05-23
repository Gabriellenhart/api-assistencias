# Fases de Migração DEV -> PROD (Base Canônica PROD)

## Fase A - Baixo risco
- Permitir status `Agendado` em OS.
- Endpoint `GET /usinas/todas-usinas`.
- Utilitários de apoio: `generate_insomnia.py`, `insomnia_collection.json`, `check_schema.py`, `backup_plain.py`.

## Fase B - Médio risco
- Campos operacionais de usuário:
  - `horario_inicio`, `horario_fim`, `latitude_base`, `longitude_base`.
- Tabela/configuração operacional.
- Histórico de planejamento.

## Fase C - Alto risco
- Motor de planejamento completo (`planning_*`, `execution_*`, serviços).
- Endpoints avançados de planejamento/execução.
- Automações de OS/chamado.

## Regra de promoção por fase
1. Aplicar migrations em staging (clone de produção).
2. Executar testes automatizados + smoke test de rotas críticas.
3. Validar integração SolarZ e scheduler.
4. Deploy controlado na VPS.
5. Monitorar e manter plano de rollback.
