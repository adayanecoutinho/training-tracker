# AGENTS.md — training-tracker

## Contexto

Projeto de acompanhamento de treino de musculação.

- **Hevy** (app de treino) é a fonte primária de registro de musculação. API em https://api.hevyapp.com/docs, header `api-key` lido de `HEVY_API_KEY` no `.env`.
- **Strava** é a fonte do cardio.
- **Banco** Postgres 13+ via `DATABASE_URL` (por padrão, Supabase local em Docker) guarda os dados estruturados para análise.
- **Logs do Obsidian** (pasta em `OBSIDIAN_LOGS_DIR`, padrão `examples/obsidian` com dados fictícios) guardam logs manuais antigos de treino. As regras de treino moram nas notas de metodologia, fora deste repositório.
- Papéis: um agente implementa, outro define a metodologia e avalia os treinos. Não invente regras de treino; onde a regra for metodológica, deixe o campo ou a função preparada e marcada com `TODO(metodologia)`.

## Regras invioláveis

1. **As notas do Obsidian são somente leitura por padrão.** Agentes só escrevem numa pasta de inbox dedicada. Qualquer outra escrita, movimentação ou exclusão exige autorização explícita na conversa, para aquela alteração, e um backup antes. Relatórios vão para `reports/` dentro do projeto. Não mude o formato de `treinos-*-2026.md`: o código lê esses arquivos.
2. Nunca imprimir, logar ou commitar a API key, tokens ou o `.env`. O `.env` e o `data/` ficam fora do git.
3. Todo import e sync precisa ser **idempotente**: rodar duas vezes não duplica dados (upsert por chave natural).
4. Python 3.12+. Prefira a stdlib. Dependências permitidas: `psycopg[binary]`. Declare em `requirements.txt`.
5. Scripts rodam com `python <script>.py`.
6. **Documentação com descoberta progressiva** (vale para `docs/`):
   - Uma ideia por arquivo, de 20 a 60 linhas; um índice por área com "arquivo | quando abrir".
   - Frontmatter com `description:` de uma linha; links com a conclusão ao lado.
   - Uma regra mora em um só lugar. Ao ler, comece pelo índice e abra só o necessário.
7. **Ritual de entrega:** nenhuma tarefa está pronta sem, no mesmo commit, atualizar `docs/como-funciona.md`, tirar o item de `docs/backlog/` e registrar em `docs/entregas.md` (detalhes em `docs/README.md`).

## Onde está cada coisa

| Arquivo | Abra quando |
|---|---|
| `README.md` | precisar rodar o projeto (banco, sync, relatório, Strava) |
| `ARCHITECTURE.md` | quiser os componentes, o fluxo de dados e as garantias |
| `docs/README.md` | quiser o índice da documentação e o ritual de entrega |
| `docs/como-funciona.md` | precisar saber o que o sistema faz hoje (scripts, banco, regras de dados) |
| `docs/adr/README.md` | quiser saber por que uma decisão de arquitetura foi tomada |
| `docs/backlog/README.md` | for começar trabalho novo |
| `docs/entregas.md` | quiser o histórico do que foi entregue |
