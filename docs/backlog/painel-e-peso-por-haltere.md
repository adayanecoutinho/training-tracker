---
description: Painel único de acompanhamento e o pré-requisito de normalizar o peso de halteres na análise.
---

# Painel e peso por haltere

> Parte do [backlog](README.md).

## Pré-requisito: peso por haltere (fazer junto com o painel)

Normalizar o peso de halteres para "peso de um haltere" na análise, sem alterar o Hevy. Alguns exercícios podem ter sido registrados pelo total das duas mãos até uma data de corte; depois, por haltere.

- Manter uma tabela de exceções (exercício, data de corte, regra: dividir por 2 ou "equipamento incerto").
- Criar coluna ou view `weight_per_dumbbell_kg` e usá-la em `v_exercise_progression`, `report.py` e `load_steps.py`.
- Distinguir templates de halter e de barra do mesmo movimento: nunca dividir cargas registradas como barra.

Até lá, o relatório pode mostrar queda aparente nesses exercícios: é mudança de convenção, não regressão.

## Painel

Quando houver algumas semanas de dados limpos, propor um painel único com:
- progressão por exercício;
- volume semanal por músculo;
- aderência (treinos por semana, semanas válidas do bloco);
- cardio semanal.

Antes de implementar, apresentar as opções (ex.: Metabase, página estática gerada pelo job agendado, Supabase Studio, dashboard no Obsidian).

## Pronto quando
- Exercícios com halteres aparecem sem queda artificial no relatório e nos degraus de carga.
- O painel abre no celular e se atualiza sozinho depois do sync.
