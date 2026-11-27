"""Gera/reconcilia CSV de nomes do Hevy e Obsidian para revisão manual."""

import csv
from pathlib import Path

from import_hevy import load
from obsidian_parser import logs, normalized
from canonical_aliases import canonical
from import_obsidian import rows_for_session
from db import connect

CSV_PATH = Path(__file__).resolve().parent / "exercise_aliases.csv"

def run():
    existing = {}
    if CSV_PATH.exists():
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as file:
            existing = {(row["source"], row["name"]): row["canonical_name"]
                        for row in csv.DictReader(file)}
    hevy_names = {e["title"].strip() for w in load("workouts")
                  for e in w.get("exercises", []) if e.get("title")}
    # Inclui treinos recentes da sincronização, ainda ausentes do dump local.
    with connect() as conn:
        rows_in_db = conn.execute(
            "SELECT DISTINCT BTRIM(e.name) FROM sets s "
            "JOIN workouts w ON w.id=s.workout_id "
            "JOIN exercises e ON e.id=s.exercise_id "
            "WHERE w.source='hevy' AND w.deleted_at IS NULL"
        ).fetchall()
    hevy_names.update(name for (name,) in rows_in_db if name)
    obs_names = {row["exercise"] for (day, title), rows in logs().items()
                 for row in rows_for_session(title, rows)}
    obs_index = {normalized(name): name for name in sorted(obs_names)}
    rows = []
    for source, names in (("hevy", hevy_names), ("obsidian", obs_names)):
        for name in sorted(names, key=str.casefold):
            key = (source, name)
            value = canonical(name)
            if not value:
                value = existing.get(key) or (obs_index.get(normalized(name), "") if source == "hevy" else "")
            rows.append({"source": source, "name": name, "canonical_name": value})
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["source", "name", "canonical_name"])
        writer.writeheader()
        writer.writerows(rows)
    unresolved = [row for row in rows if not row["canonical_name"]]
    pending_path = CSV_PATH.parent / "reports" / "aliases-pendentes.md"
    pending_path.parent.mkdir(exist_ok=True)
    pending_path.write_text(
        "# Exercícios pendentes de mapeamento\n\n"
        f"Total: {len(unresolved)} nomes do Hevy/Obsidian.\n"
        "Somente nomes usados em sessões; sem equivalência inequívoca, o canonical_name permanece vazio no CSV.\n\n" +
        "\n".join(f"- {row['source']}: {row['name']}" for row in unresolved) + "\n",
        encoding="utf-8",
    )
    print(f"CSV: {len(rows)} nomes, {len(unresolved)} sem mapeamento; {CSV_PATH}")
    for row in unresolved:
        print(f"  {row['source']}: {row['name']}")


if __name__ == "__main__":
    run()
