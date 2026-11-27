"""Confere amostras das views com o backup e contagens do Postgres."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from db import connect
from import_hevy import load


def counts(conn):
    with conn.cursor() as cur:
        return {table: (cur.execute(f"SELECT COUNT(*) FROM {table}"), cur.fetchone()[0])[1]
                for table in ("exercises", "workouts", "sets", "body_metrics")}


def sample_checks(conn, quantity=2):
    workouts = [w for w in load("workouts") if w.get("exercises")][:quantity]
    for workout in workouts:
        effective = sum(1 for e in workout["exercises"] for s in e.get("sets", [])
                        if s.get("type") != "warmup")
        tonnage = sum(Decimal(str(s["weight_kg"])) * Decimal(str(s["reps"]))
                      for e in workout["exercises"] for s in e.get("sets", [])
                      if s.get("weight_kg") is not None and s.get("reps") is not None)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT v.effective_sets,v.tonnage_kg FROM v_session_summary v "
                "JOIN workouts w ON w.id=v.workout_id WHERE w.hevy_id=%s", (workout["id"],)
            )
            result = cur.fetchone()
        if result != (effective, tonnage):
            raise AssertionError(
                f"Treino {workout['id']}: view={result}, JSON={(effective, tonnage)}"
            )
        print(f"Conferido treino {str(workout['id'])[:8]}: {effective} séries, {tonnage} kg")


def weekly_volume_check(conn):
    """Confere a view agregando os registros individualmente no Python."""
    rows = conn.execute(
        "SELECT (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date,"
        " e.primary_muscle,e.secondary_muscles"
        " FROM sets s JOIN workouts w ON w.id=s.workout_id"
        " JOIN exercises e ON e.id=s.exercise_id"
        " WHERE w.deleted_at IS NULL AND s.set_type<>'warmup'"
    ).fetchall()
    actual = defaultdict(Decimal)
    for day, primary, secondary in rows:
        week_start = day - timedelta(days=day.weekday())
        if primary:
            actual[week_start, primary] += Decimal('1')
        for muscle in set(secondary or ()) - {primary, ''}:
            actual[week_start, muscle] += Decimal('0.5')
    in_view = {(week_start, muscle): total for week_start, muscle, total in conn.execute(
        "SELECT week_start,muscle,effective_sets FROM v_weekly_volume_by_muscle"
    )}
    if actual != in_view:
        differences = {key for key in actual.keys() | in_view.keys()
                       if actual.get(key, 0) != in_view.get(key, 0)}
        raise AssertionError(f"Divergências no volume semanal: {len(differences)}")
    print(f"Volume semanal conferido: {len(rows)} séries, "
          f"{len(actual)} combinações semana/músculo, iguais às da view")


if __name__ == "__main__":
    with connect() as conn:
        sample_checks(conn)
        weekly_volume_check(conn)
        print("Contagens:", counts(conn))
