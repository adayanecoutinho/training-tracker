"""Sincroniza eventos atualizados/removidos do Hevy; reexecução segura."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import hevy
from db import connect
from import_hevy import import_backup, upsert_workout

STATE_KEY = "hevy_events_since"


def backup_timestamp():
    path = Path(__file__).resolve().parent / "data" / "raw" / "_dumped_at.txt"
    if not path.exists():
        return "1970-01-01T00:00:00Z"
    value = datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    if value.tzinfo is None:
        try:
            value = value.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        except ZoneInfoNotFoundError:
            value = value.replace(tzinfo=timezone(timedelta(hours=-3)))
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sync():
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM sync_state WHERE key=%s", (STATE_KEY,))
            row = cur.fetchone()
        if row is None:
            import_backup(conn)
            since = backup_timestamp()
        else:
            since = row[0]

        events = list(hevy.paginate("/v1/workouts/events", "events", since=since))
        updated = deleted = 0
        with conn.transaction():
            with conn.cursor() as cur:
                # A API lista do mais recente ao mais antigo; processar na ordem inversa.
                for event in reversed(events):
                    kind = event.get("type")
                    if kind == "updated":
                        workout = event.get("workout")
                        if not isinstance(workout, dict):
                            raise ValueError("Evento updated sem objeto workout")
                        upsert_workout(cur, workout)
                        updated += 1
                    elif kind == "deleted":
                        hevy_id = event.get("id")
                        if not hevy_id or not event.get("deleted_at"):
                            raise ValueError("Evento deleted sem id/deleted_at")
                        cur.execute(
                            "UPDATE workouts SET deleted_at=%s WHERE hevy_id=%s",
                            (event["deleted_at"], str(hevy_id)),
                        )
                        deleted += 1
                    else:
                        raise ValueError(f"Evento não reconhecido: {kind!r}")
                # Watermark anterior ao download: edições concorrentes reaparecem na próxima rodada.
                cur.execute(
                    "INSERT INTO sync_state(key,value) VALUES (%s,%s) "
                    "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                    (STATE_KEY, started_at),
                )
    print(f"Sync: {len(events)} eventos ({updated} atualizados, {deleted} removidos)")


if __name__ == "__main__":
    sync()
