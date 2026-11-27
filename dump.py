"""Baixa todo o histórico do Hevy em JSON bruto (backup local, base para a importação)."""

import json
from datetime import datetime

import hevy

OUT = hevy.ROOT / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

sources = {
    "workouts": ("/v1/workouts", "workouts"),
    "routines": ("/v1/routines", "routines"),
    "body_measurements": ("/v1/body_measurements", "body_measurements"),
    "exercise_templates": ("/v1/exercise_templates", "exercise_templates"),
}

for name, (path, key) in sources.items():
    items = list(hevy.paginate(path, key))
    (OUT / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{name}: {len(items)} registros")

(OUT / "_dumped_at.txt").write_text(datetime.now().isoformat(), encoding="utf-8")
print(f"Salvo em {OUT}")
