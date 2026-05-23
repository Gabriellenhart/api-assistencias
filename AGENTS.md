# AGENTS.md

## Orientações para futuras tarefas

- Idioma preferencial: português do Brasil.
- Não fazer refatorações grandes sem pedido explícito.
- Preservar compatibilidade com produção, especialmente no núcleo de chamados/assistências.
- Preferir sempre mudanças incrementais, conservadoras e revisáveis.
- Não versionar segredos, dumps, uploads reais, logs, backups ou bancos locais.
- Rodar testes e lint quando disponíveis; se não for possível, documentar o motivo.
- Antes de alterar migrations, revisar impacto em produção e compatibilidade com bancos já migrados.
- Não alterar contratos de API, nomes de rotas, payloads públicos ou modelos sem documentar claramente.
- Manter documentação atualizada quando scripts, deploy, backup ou variáveis de ambiente mudarem.
- Evitar reestruturações amplas de módulos incompletos nesta fase do projeto.
- Antes de mexer em scripts de desenvolvimento, rodar `scripts/dev/check.sh` quando o ambiente permitir.
- Nunca executar `scripts/dev/reset_db.sh` contra produção ou contra URIs que pareçam produção.
- Manter scripts de desenvolvimento idempotentes: não sobrescrever `.env`, não imprimir segredos e falhar com mensagens claras.
- Documentar alterações de fluxo local no `README.md` e em `docs/development/LOCAL_SETUP.md`.
