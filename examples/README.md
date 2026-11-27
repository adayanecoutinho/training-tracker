# Fictional demo data

Everything here is invented for the quick start. No value comes from real training.

| Path | Format | Read by |
|---|---|---|
| `hevy/*.json`, `hevy/_dumped_at.txt` | Same files `dump.py` writes to `data/raw/` | `import_hevy.py`, `sync.py`, `verify.py` |
| `obsidian/04-Logs e Aprendizados/treinos-<mês>-2026.md` | Markdown log table: Data, Treino, Exercício, Peso (kg), Reps, RPE, RIR, Cardio, Notas | `obsidian_parser.py` (default `OBSIDIAN_LOGS_DIR`) |

The April log shares a date with one Hevy workout, to show the merge: the importer fills RIR and notes on the Hevy sets instead of creating a second workout. `16 (2×8)` shows the per-dumbbell convention (stored as 8 kg, original text kept in the set note).
