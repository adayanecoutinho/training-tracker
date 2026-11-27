---
description: Riscos conhecidos nos importadores, ainda sem correção.
---

# Riscos de modelagem

> Parte do [backlog](README.md). Não quebram nada hoje, mas podem gerar dado errado sem aviso.

1. **Pareamento Obsidian × Hevy por posição** (`import_obsidian.py`, `match_records`): RIR e notas do Obsidian entram na série de mesma posição, sem conferir reps, carga ou duração. Correção: exigir igualdade por par e contar divergentes como não casados.
2. **RIR antigo preso à posição** (`import_hevy.py`, `rir=sets.rir`): se o Hevy trocar o exercício daquele slot, o RIR antigo fica no novo. Correção: zerar o RIR quando `exercise_id` mudar.
3. **Notas do Obsidian na descrição do Hevy** (`merge_session`): mistura fontes e sobrevive mesmo se o Hevy limpar a descrição. Correção: coluna ou marca própria.
4. **Duplicata tardia:** dia sem Hevy vira sessão `obsidian`; se o Hevy daquele dia chegar depois, fica duplicado. Correção: reconciliar por data também após o sync.
5. **Testes:** `merge_session`, `match_records` e `rows_for_session` não têm teste.

## Pronto quando
Cada item corrigido ou aceito conscientemente (registrado em [entregas](../entregas.md)), e os testes do item 5 existem.
