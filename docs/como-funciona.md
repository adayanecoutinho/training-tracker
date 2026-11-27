---
description: Como o projeto funciona hoje (fontes, scripts, banco, relatórios e regras de dados). Atualize a cada entrega do backlog.
---

# Como funciona hoje

> Estado atual do sistema, não o histórico de como chegou aqui. Itens futuros ficam em [backlog/](backlog/README.md).
> Como rodar cada comando: [README.md](../README.md). Visão geral e garantias: [ARCHITECTURE.md](../ARCHITECTURE.md).

## Visão geral

```
Hevy (musculação) ──dump.py / sync.py──┐
Strava (cardio) ────sync_strava.py─────┼──> Postgres ──report.py──> reports/relatorio-AAAA-MM-DD.md ──> coach (agents/coach.md)
Logs do Obsidian ───import_obsidian.py─┘        └──load_steps.py──> reports/cargas-*.md
```

- **Fonte única por tipo:** musculação vem do Hevy; cardio vem do Strava; logs manuais antigos vêm do Obsidian (somente leitura).
- **Banco:** qualquer Postgres 13+ apontado por `DATABASE_URL` (padrão: Supabase local na porta 58322). Configuração lida do `.env` por `env.py`.
- **Execução:** manual, ou agendada com `job.py` (ver abaixo). A imagem do `Dockerfile` roda os scripts como tarefas agendadas.

## Banco

O schema mora nas migrations em `supabase/migrations/` (SQL puro, fonte única; não copie o schema para cá).

| Objeto | Para que serve |
|---|---|
| `exercises` | catálogo de exercícios, com `canonical_name` (nome padronizado pt-BR) e músculos do template do Hevy |
| `exercise_hevy_templates` | todos os templates do Hevy que apontam para o mesmo exercício canônico |
| `workouts`, `sets` | treinos e séries; `source` = `hevy` ou `obsidian`; `deleted_at` para remoções do Hevy |
| `cardio_sessions` | atividades do Strava, sem mapa, coordenadas nem localização |
| `body_metrics`, `daily_checkins` | medidas e check-ins diários genéricos (sono, energia, notas); estrutura pronta, pouco usada |
| `mesocycles`, `mesocycle_weeks` | calendário de blocos de treino (estrutura pronta, ainda não preenchida) |
| `sync_state` | cursores dos syncs (`hevy_events_since`, `strava_last_start`) |
| `v_session_summary` | por treino: duração, séries efetivas, tonelagem, RPE médio |
| `v_weekly_volume_by_muscle` | séries por semana ISO e músculo (primário 1, secundário 0,5; aquecimento não conta) |
| `v_exercise_progression` | melhor série por exercício e treino (e1RM de Epley) |
| `v_weekly_cardio` | sessões, sessões ≥ 20 min, minutos e km por semana |

## Scripts

**Coleta**
- `check.py`: testa a API do Hevy sem gravar nada.
- `dump.py`: baixa todo o histórico do Hevy e os `exercise_templates` para `data/raw/`.
- `import_hevy.py`: importa o backup JSON no banco (transacional, idempotente). Preserva RIR e notas vindos do Obsidian ao reimportar.
- `sync.py`: incremental por `/v1/workouts/events`; trata `updated` (substitui as séries) e `deleted` (preenche `deleted_at`). Sem cursor, faz o import completo.
- `strava_auth.py` (uma vez) e `sync_strava.py`: cardio incremental. **Ignora cópias do Hevy** (`WeightTraining` ou descrição "Registrado com hevyapp.com"). Respeita limites e renova o token sozinho.
- `import_obsidian.py` + `obsidian_parser.py`: lê os logs `treinos-<mês>-2026.md` (pasta em `OBSIDIAN_LOGS_DIR`, padrão `examples/obsidian`). Em data que já tem treino do Hevy, enriquece em vez de duplicar. Gera `reports/importacao-obsidian.md`.

**Nomes de exercício**
- `generate_aliases.py` gera `exercise_aliases.csv`; `canonical_aliases.py` tem as equivalências óbvias e **tem prioridade sobre o CSV**; `apply_aliases.py` aplica e une exercícios com o mesmo nome canônico. Nomes incertos ficam sem correspondência até revisão humana.

**Relatórios** (descritivos, sem recomendações)
- `report.py --weeks N | --since AAAA-MM-DD | --all`: sessões, volume semanal por músculo (com as datas), progressão dos 10 exercícios mais frequentes, falhas e RPE ≥ 9,5, variações de carga acima de 50%, semanas sem treino e cardio.
- `load_steps.py`: degraus de carga já usados por exercício (`cargas-por-exercicio.md` e histórico completo), sinalizando pesos usados uma vez só e possíveis trocas de máquina/escala.
- **Histórico comparável:** `history_config.py` lê `TRAINING_HISTORY_START` (padrão fictício `2026-01-05`). `report.py` sem argumentos começa nesse corte; `--weeks` respeita o mesmo limite, `--since` permite outro recorte explícito e `--all` inclui tudo.
- `verify.py`: confere amostras de `v_session_summary` contra o JSON do backup e recalcula toda a `v_weekly_volume_by_muscle` em Python.

**Tarefas agendadas**
- `job.py sync | relatorio`: executa a tarefa e avisa um serviço de health check compatível com Healthchecks.io (`/start`, sucesso ou `/fail`). `sync` = `sync.py` + `sync_strava.py`; `relatorio` = `report.py --weeks 8` + `load_steps.py`. A URL de ping vem das variáveis `HEALTHCHECK_URL_SYNC` e `HEALTHCHECK_URL_RELATORIO`, nunca é impressa e a saída da tarefa não vai no aviso. Falha ao avisar não derruba a tarefa.

**Hook de pre-commit** (`.githooks/pre-commit`, ativo com `git config core.hooksPath .githooks`): bloqueia commit que mexe em `.py` (exceto `test_*.py`), migrations ou `requirements.txt` sem `docs/como-funciona.md` e `docs/entregas.md` juntos. Pular uma vez: `SKIP_DOCS_CHECK=1 git commit`.

**Imagem** (`Dockerfile`): Python + psycopg, sem porta, usuário sem privilégio; o processo principal só mantém o container vivo e os scripts rodam como tarefas agendadas. O healthcheck só confere que o Python e as dependências carregam, sem testar o banco. O `strava_tokens.json` é gravado com permissão 600. `init_db.py` aplica as migrations num Postgres sem Supabase.

**Agente coach** (`agents/coach.md`): prompt do agente (identidade, fontes em ordem, limites, rotinas, formato para celular). Não copia regras: aponta para as notas de metodologia, só leitura, e escreve apenas na inbox.

**Apoio:** `env.py`, `db.py`, `hevy.py`, `strava_client.py`, testes em `test_*.py`. `migrate_to_supabase.py` copia dados entre dois Postgres locais.

## Regras de dados que o código assume

- Imports e syncs são idempotentes (upsert por chave natural): rodar duas vezes não muda contagens.
- Segredos só no `.env` e em `data/strava_tokens.json`, fora do git; nada disso é impresso.
- **Halteres:** `16 (2×8)` no Obsidian é registrado como 8 kg por haltere, com o texto original na nota da série.
- Regras de treino não ficam no código: moram nas notas de metodologia. Campos metodológicos ficam marcados com `TODO(metodologia)`.

## Limitações conhecidas

Riscos de modelagem (pareamento Obsidian × Hevy por posição, notas do Obsidian na descrição do Hevy, sessões duplicadas se o Hevy chegar depois): ver [backlog](backlog/README.md).
