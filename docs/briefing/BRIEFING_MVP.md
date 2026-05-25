Etapa 2 — Criar docs/briefing/BRIEFING_MVP.md

Esse arquivo documenta o que é o módulo Briefing Operacional, como ele funciona e quais regras usa.

Crie o arquivo:

nano docs/briefing/BRIEFING_MVP.md

Cole exatamente este conteúdo:

# Briefing Operacional Diário — MVP

## 1. Objetivo

O módulo **Briefing Operacional Diário** tem como objetivo gerar uma visão resumida das pendências operacionais do sistema, começando inicialmente pelos **chamados**.

A ideia é ajudar o usuário a encerrar ou iniciar o dia de trabalho com clareza sobre:

- quais chamados precisam de ação;
- quais chamados estão atrasados;
- quais chamados estão sem prazo definido;
- quais chamados estão sem responsável;
- quais chamados estão sem atualização recente;
- qual foi a última ação identificada;
- qual é a próxima ação sugerida;
- qual é a prioridade operacional calculada.

Este MVP não altera dados. Ele apenas lê as informações existentes e gera um resumo operacional.

---

## 2. Escopo do MVP

Nesta primeira versão, o briefing considera apenas:

```text
Chamados

Ainda não entram neste MVP:

Orçamentos
Ordens de serviço
Garantias
Tarefas operacionais persistidas
Snapshots diários
Frontend
3. O que o módulo entrega

O endpoint retorna duas partes principais:

resumo
tarefas
3.1. Resumo

O bloco resumo contém contadores gerais:

{
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
}
3.2. Tarefas

O bloco tarefas contém a lista resumida dos chamados que precisam de acompanhamento.

Cada item representa uma pendência operacional derivada de um chamado.

4. Endpoint do MVP
GET /briefing/diario

O endpoint é protegido por autenticação JWT.

5. Parâmetros disponíveis
Parâmetro	Tipo	Obrigatório	Padrão	Descrição
escopo	string	não	chamados	Define o escopo do briefing. No MVP, somente chamados é aceito.
data	string	não	data atual	Data de referência no formato YYYY-MM-DD.
responsavel_id	integer	não	null	Filtra chamados por responsável quando houver campo compatível no model.
limite	integer	não	50	Quantidade máxima de tarefas retornadas. Máximo: 200.
6. Critérios para um chamado entrar no briefing

Um chamado entra no briefing quando:

não está finalizado;
possui alguma condição operacional relevante;
precisa de acompanhamento ou continuidade.

No MVP, chamados não finalizados entram na análise e recebem score conforme as regras de prioridade operacional.

7. Status considerados finalizados

Um chamado é ignorado pelo briefing quando o status normalizado for um dos seguintes:

resolvido
concluido
concluído
cancelado
fechado
finalizado

A normalização ignora:

letras maiúsculas/minúsculas;
acentos;
espaços extras.

Exemplos:

"Concluído" -> "concluido"
"RESOLVIDO" -> "resolvido"
" Cancelado " -> "cancelado"
8. Regras de prazo

O MVP tenta identificar um prazo usando os campos disponíveis no chamado.

Campos considerados, quando existirem:

data_agendamento
data_limite
prazo
prazo_resolucao
data_limite_resolucao

A classificação de prazo pode ser:

Status de prazo	Descrição
sem_prazo	Nenhum prazo foi identificado.
atrasado	O prazo é anterior à data de referência.
vence_hoje	O prazo é igual à data de referência.
vence_amanha	O prazo é igual ao dia seguinte da data de referência.
futuro	O prazo é posterior ao dia seguinte da data de referência.
9. Regras de score operacional

O score operacional define a urgência da tarefa.

O valor máximo é 100.

Condição	Pontuação
Chamado atrasado	+50
Prioridade original crítica	+35
Prioridade original alta	+25
Vence hoje	+25
Vence amanhã	+15
Sem responsável	+20
Sem prazo	+15
Sem atualização há 2 dias ou mais	+15
Aguardando cliente	+10
10. Prioridade operacional

A prioridade operacional é calculada a partir do score:

Score	Prioridade
80 a 100	critica
60 a 79	alta
30 a 59	media
0 a 29	baixa

Essa prioridade é diferente da prioridade original do chamado.

A prioridade original vem do próprio chamado.
A prioridade operacional é calculada pelo briefing com base no contexto atual.

11. Próxima ação sugerida

O backend gera uma próxima ação sugerida com base nas condições do chamado.

Condição	Próxima ação sugerida
Sem responsável	Definir responsável pelo atendimento.
Atrasado	Revisar urgência, atualizar o cliente e registrar plano de ação.
Vence hoje	Resolver ou posicionar o cliente ainda hoje.
Sem prazo	Definir prazo e próxima etapa do atendimento.
Aguardando cliente	Cobrar retorno do cliente.
Sem atualização recente	Revisar andamento e registrar uma atualização.
Nenhuma condição específica	Revisar chamado e confirmar próxima ação.
12. Exemplo de tarefa retornada
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
13. Ordenação das tarefas

As tarefas são ordenadas por:

maior score;
prazo mais próximo;
maior quantidade de dias sem atualização;
ID mais recente.

Isso faz com que os itens mais críticos apareçam no topo.

14. Limitações do MVP

Este MVP:

considera somente chamados;
não cria registros no banco;
não cria tabela nova;
não cria migrations;
não altera o schema;
não cria tarefas operacionais persistidas;
não cria snapshots diários;
não implementa frontend;
não envia notificações;
não altera status de chamados;
não cria comentários automaticamente.
15. Próximas fases sugeridas
Fase 2 — Integração frontend

Criar tela no frontend para exibir:

cards de resumo;
lista de tarefas;
filtros por prioridade;
filtros por status de prazo;
botão para abrir chamado.
Fase 3 — Ações rápidas

Adicionar ações como:

abrir chamado;
criar lembrete;
adicionar comentário;
definir prazo;
atribuir responsável.
Fase 4 — Tarefas operacionais

Criar tabela tarefas_operacionais para persistir próximas ações.

Fase 5 — Snapshot diário

Criar histórico de briefings gerados por dia.

Fase 6 — Expansão do escopo

Incluir:

orçamentos;
ordens de serviço;
garantias.
16. Observação importante

O Briefing Operacional não substitui os módulos existentes.

Ele funciona como uma camada de leitura e priorização sobre os dados já existentes.


Salve com:

```text
CTRL + O
ENTER
CTRL + X