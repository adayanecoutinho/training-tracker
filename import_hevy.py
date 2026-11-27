"""Importação transacional e idempotente do backup JSON do Hevy."""

import json
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from db import connect

RAW = Path(__file__).resolve().parent / "data" / "raw"
SET_TYPES = {"warmup", "normal", "failure", "dropset"}


def load(name):
    return json.loads((RAW / (name + ".json")).read_text(encoding="utf-8"))


def ensure_exercise(cur, template_id, title, muscle=None, secondary=None, equipment=None):
    template_id = str(template_id) if template_id is not None else None
    if template_id:
        cur.execute(
            "SELECT exercise_id FROM exercise_hevy_templates WHERE template_id=%s",
            (template_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE exercises SET name=%s, primary_muscle=COALESCE(%s, primary_muscle), "
                "secondary_muscles=COALESCE(%s, secondary_muscles), "
                "equipment=COALESCE(%s, equipment) WHERE id=%s",
                (title, muscle, secondary, equipment, row[0]),
            )
            return row[0]
        cur.execute("SELECT id FROM exercises WHERE hevy_template_id=%s", (template_id,))
        row = cur.fetchone()
        if row:
            exercise_id = row[0]
            cur.execute(
                "UPDATE exercises SET name=%s, primary_muscle=COALESCE(%s, primary_muscle), "
                "secondary_muscles=COALESCE(%s, secondary_muscles), equipment=COALESCE(%s, equipment) "
                "WHERE id=%s", (title, muscle, secondary, equipment, exercise_id),
            )
        else:
            cur.execute(
                "INSERT INTO exercises (hevy_template_id,name,canonical_name,primary_muscle,secondary_muscles,equipment) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (template_id, title, title, muscle, secondary or [], equipment),
            )
            exercise_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO exercise_hevy_templates(template_id,exercise_id) VALUES (%s,%s) "
            "ON CONFLICT(template_id) DO UPDATE SET exercise_id=EXCLUDED.exercise_id",
            (template_id, exercise_id),
        )
        return exercise_id
    # Exercícios sem template: reutilizar pelo nome exato da fonte.
    cur.execute("SELECT id FROM exercises WHERE hevy_template_id IS NULL AND name=%s LIMIT 1", (title,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO exercises(name,canonical_name) VALUES (%s,%s) RETURNING id", (title, title))
    return cur.fetchone()[0]


def upsert_templates(cur, templates):
    for item in templates:
        ensure_exercise(
            cur, item["id"], item.get("title") or item["id"],
            item.get("primary_muscle_group"), item.get("secondary_muscle_groups") or [],
            item.get("equipment"),
        )


def upsert_workout(cur, workout):
    hevy_id = str(workout["id"])
    cur.execute(
        "INSERT INTO workouts(source,hevy_id,title,description,routine_id,start_time,end_time,updated_at,deleted_at) "
        "VALUES ('hevy',%s,%s,%s,%s,%s,%s,%s,NULL) "
        "ON CONFLICT(hevy_id) DO UPDATE SET title=EXCLUDED.title, "
        "description=COALESCE(NULLIF(EXCLUDED.description,''),workouts.description), "
        "routine_id=EXCLUDED.routine_id, start_time=EXCLUDED.start_time, "
        "end_time=EXCLUDED.end_time, updated_at=EXCLUDED.updated_at, deleted_at=NULL "
        "RETURNING id",
        (hevy_id, workout.get("title"), workout.get("description"),
         workout.get("routine_id"), workout["start_time"], workout.get("end_time"),
         workout.get("updated_at")),
    )
    workout_id = cur.fetchone()[0]
    retained = []
    for exercise_position, exercise in enumerate(workout.get("exercises") or []):
        position = exercise_position  # posição da lista é a chave estável usada no backup
        template_id = exercise.get("exercise_template_id")
        exercise_id = ensure_exercise(
            cur, template_id, exercise.get("title") or str(template_id) or "Sem nome"
        )
        for set_position, item in enumerate(exercise.get("sets") or []):
            set_type = item.get("type") or "normal"
            if set_type not in SET_TYPES:
                raise ValueError(f"Tipo de série Hevy desconhecido: {set_type!r}")
            retained.append((position, set_position))
            cur.execute(
                "INSERT INTO sets(workout_id,exercise_id,exercise_order,set_index,set_type,weight_kg,reps,"
                "duration_seconds,distance_meters,rpe,rir,notes) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s) "
                "ON CONFLICT(workout_id,exercise_order,set_index) DO UPDATE SET "
                "exercise_id=EXCLUDED.exercise_id,set_type=EXCLUDED.set_type,"
                "weight_kg=EXCLUDED.weight_kg,reps=EXCLUDED.reps,"
                "duration_seconds=EXCLUDED.duration_seconds,distance_meters=EXCLUDED.distance_meters,"
                "rpe=EXCLUDED.rpe,rir=sets.rir,"
                "notes=CASE WHEN sets.notes LIKE '%%[Obsidian]%%' THEN sets.notes "
                "ELSE COALESCE(EXCLUDED.notes,sets.notes) END",
                (workout_id, exercise_id, position, set_position, set_type,
                 item.get("weight_kg"), item.get("reps"), item.get("duration_seconds"),
                 item.get("distance_meters"), item.get("rpe"), exercise.get("notes")),
            )
    # Remove apenas posições desaparecidas, preservando IDs de séries inalteradas.
    cur.execute("SELECT exercise_order,set_index FROM sets WHERE workout_id=%s", (workout_id,))
    removed = set(cur.fetchall()) - set(retained)
    for position, index in removed:
        cur.execute(
            "DELETE FROM sets WHERE workout_id=%s AND exercise_order=%s AND set_index=%s",
            (workout_id, position, index),
        )
    return workout_id


def upsert_metrics(cur, measurements):
    for entry in measurements:
        day = date.fromisoformat(str(entry["date"])[:10])
        extras = {k: v for k, v in entry.items() if k not in
                  {"id", "date", "created_at", "weight_kg", "fat_percent"} and v is not None}
        cur.execute(
            "INSERT INTO body_metrics(date,weight_kg,body_fat_pct,lean_mass_kg,measurements,source) "
            "VALUES (%s,%s,%s,%s,%s,'hevy') "
            "ON CONFLICT(date) DO UPDATE SET weight_kg=EXCLUDED.weight_kg, "
            "body_fat_pct=EXCLUDED.body_fat_pct,lean_mass_kg=EXCLUDED.lean_mass_kg, "
            "measurements=EXCLUDED.measurements,source=EXCLUDED.source",
            (day, entry.get("weight_kg"), entry.get("fat_percent"),
             entry.get("lean_mass_kg"), Jsonb(extras)),
        )


def import_backup(conn):
    templates, workouts, metrics = (load(n) for n in
                                   ("exercise_templates", "workouts", "body_measurements"))
    with conn.transaction():
        with conn.cursor() as cur:
            upsert_templates(cur, templates)
            for workout in workouts:
                upsert_workout(cur, workout)
            upsert_metrics(cur, metrics)
    print(f"Backup importado: {len(templates)} templates, {len(workouts)} treinos, {len(metrics)} medições")


if __name__ == "__main__":
    with connect() as connection:
        import_backup(connection)
