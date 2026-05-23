# Baseline para GitHub

## Objetivo

Preparar uma baseline limpa e segura do projeto `api-assistencias` para o primeiro commit no GitHub, com mudanças incrementais e sem refatoração estrutural.

## O que foi limpo

- Artefatos Python locais: `__pycache__` e arquivos `*.pyc`.
- Cache local do pytest.
- Arquivos locais de logs, dumps, backups e bancos SQLite quando encontrados.
- Uploads reais em `api/static/uploads`, mantendo somente `.gitkeep`.
- Regras de `.gitignore` para impedir versionamento de `.env`, logs, bancos locais, dumps, backups e uploads reais.

## O que foi ajustado

- `.env.example` ampliado com variáveis de Flask, banco, CORS, uploads, SolarZ e backup.
- Log de login alterado para não registrar payload completo nem senha.
- CORS passou a usar `CORS_ORIGINS` do ambiente.
- Secrets e `DATABASE_URI` passaram a ser obrigatórios em produção.
- Credenciais SolarZ hardcoded foram removidas dos scrapers.

## O que ainda nao foi refatorado

- Estrutura dos módulos Flask, blueprints, models, schemas e services.
- Rotas públicas e contratos de API.
- Migrations já existentes.
- Scripts de produção, backup e restore, além dos ajustes mínimos de segurança.
- Módulos ainda em desenvolvimento/refatoração.

## Riscos conhecidos

- Há scripts operacionais que dependem de PostgreSQL, `pg_dump`, `pg_restore` e variáveis de ambiente corretas.
- Os testes de integração dependem de um banco PostgreSQL acessível.
- Alguns arquivos e comentários existentes possuem encoding antigo/mojibake; isso não foi corrigido nesta baseline para evitar churn.
- A busca por termos sensíveis pode apontar placeholders legítimos em documentação, scripts e testes.

## Próximos passos recomendados

- Revisar manualmente o resultado final de `grep` por segredos antes do push.
- Configurar secrets reais apenas no ambiente de produção.
- Definir `CORS_ORIGINS` explicitamente no deploy.
- Rodar testes com PostgreSQL preparado.
- Planejar correções de encoding e refatorações em tarefas separadas.

## Checklist para primeiro commit no GitHub

- [ ] Confirmar que `.env` real não está versionado.
- [ ] Confirmar que uploads reais não estão versionados.
- [ ] Confirmar que dumps, backups, logs e bancos locais não aparecem em `git status`.
- [ ] Revisar `git diff` dos arquivos alterados.
- [ ] Rodar busca por termos sensíveis e validar que restaram apenas placeholders.
- [ ] Rodar testes disponíveis ou registrar motivo de não execução.

## Checklist antes de deploy em produção

- [ ] Definir `FLASK_ENV=production`.
- [ ] Definir `SECRET_KEY` e `JWT_SECRET_KEY` com valores fortes.
- [ ] Definir `DATABASE_URI` de produção.
- [ ] Definir `CORS_ORIGINS` com domínios reais do frontend.
- [ ] Garantir que `UPLOAD_FOLDER` aponta para local persistente e com permissão correta.
- [ ] Validar backup/restore em ambiente controlado.
- [ ] Rodar migrations com revisão prévia do impacto.
