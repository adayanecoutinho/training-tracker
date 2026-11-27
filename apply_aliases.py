"""Aplica equivalências revisadas e une exercícios com mesmo nome canônico."""

import csv
from pathlib import Path

from db import connect

CSV_PATH = Path(__file__).resolve().parent / "exercise_aliases.csv"


def run():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    unresolved = [r for r in rows if not r["canonical_name"].strip()]
    mapped = [r for r in rows if r["canonical_name"].strip()]
    merged = 0
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for row in mapped:
                    source, name, canonical = (row[k].strip() for k in
                                              ("source", "name", "canonical_name"))
                    if source not in ("hevy", "obsidian"):
                        raise ValueError(f"Fonte inválida no CSV: {source}")
                    if source == "hevy":
                        cur.execute("UPDATE exercises SET canonical_name=%s WHERE BTRIM(name)=%s AND "
                                    "(hevy_template_id IS NOT NULL OR id IN "
                                    "(SELECT exercise_id FROM exercise_hevy_templates))",
                                    (canonical, name))
                    else:
                        cur.execute("UPDATE exercises SET canonical_name=%s WHERE BTRIM(name)=%s AND "
                                    "hevy_template_id IS NULL AND id NOT IN "
                                    "(SELECT exercise_id FROM exercise_hevy_templates)",
                                    (canonical, name))
                cur.execute("SELECT canonical_name FROM exercises GROUP BY canonical_name HAVING COUNT(*)>1")
                for (canonical,) in cur.fetchall():
                    cur.execute(
                        "SELECT id FROM exercises WHERE canonical_name=%s "
                        "ORDER BY (hevy_template_id IS NOT NULL) DESC, id", (canonical,)
                    )
                    ids = [r[0] for r in cur.fetchall()]
                    surviving = ids[0]
                    for duplicate in ids[1:]:
                        cur.execute("UPDATE sets SET exercise_id=%s WHERE exercise_id=%s",
                                    (surviving, duplicate))
                        cur.execute("UPDATE exercise_hevy_templates SET exercise_id=%s WHERE exercise_id=%s",
                                    (surviving, duplicate))
                        cur.execute("DELETE FROM exercises WHERE id=%s", (duplicate,))
                        merged += 1
    print(f"Mapeamentos aplicados: {len(mapped)}; exercícios unidos: {merged}")
    print(f"Sem mapeamento ({len(unresolved)}):")
    for row in unresolved:
        print(f"  {row['source']}: {row['name']}")


if __name__ == "__main__":
    run()
