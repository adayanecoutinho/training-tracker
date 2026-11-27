"""Importa logs sem modificar as notas; enriquece treinos Hevy sem duplicá-los."""

import csv
import re
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from db import connect
from obsidian_parser import logs, parsed_sets, number

ROOT = Path(__file__).resolve().parent
LOCAL_TZ = timezone(timedelta(hours=-3))
ALIAS_FILE = ROOT / "exercise_aliases.csv"


def obsidian_aliases():
    with ALIAS_FILE.open(encoding="utf-8-sig", newline="") as source:
        return {row["name"].strip(): row["canonical_name"].strip()
                for row in csv.DictReader(source) if row["source"] == "obsidian"}


def exercise_id_for(cur, name, canonical_name=None):
    canonical_name = canonical_name or name
    cur.execute(
        "SELECT id FROM exercises WHERE canonical_name=%s OR name=%s "
        "ORDER BY (hevy_template_id IS NOT NULL) DESC, id LIMIT 1", (canonical_name, name),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO exercises(name,canonical_name) VALUES (%s,%s) RETURNING id",
                (name, canonical_name))
    return cur.fetchone()[0]


def upsert_session(cur, day, title, rows, aliases, display_title=None):
    natural_key = f"obsidian:{day.isoformat()}:{title}"
    workout_id = uuid5(NAMESPACE_URL, natural_key)
    start_time = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    cur.execute(
        "INSERT INTO workouts(id,source,title,start_time) VALUES (%s,'obsidian',%s,%s) "
        "ON CONFLICT(id) DO UPDATE SET title=EXCLUDED.title,start_time=EXCLUDED.start_time",
        (workout_id, display_title or title, start_time),
    )
    orders = []
    cardio_entries = {}
    for order, row in enumerate(rows):
        if row["is_cardio"]:
            exercise_name = row["exercise"]
            if row["cardio_seconds"]:
                cardio_entries[(exercise_name, row["cardio_seconds"])] = row["notes"]
        else:
            exercise_name = row["exercise"]
            if row["cardio_seconds"]:
                cardio_name = row["cardio_name"] or "Cardio"
                cardio_entries[(cardio_name, row["cardio_seconds"])] = row["notes"]
        sets = parsed_sets(row)
        if row["is_cardio"] and row["cardio_seconds"] and not sets:
            continue
        exercise_id = exercise_id_for(cur, exercise_name, aliases.get(exercise_name))
        for index, record in enumerate(sets):
            orders.append((order, index))
            cur.execute(
                "INSERT INTO sets(workout_id,exercise_id,exercise_order,set_index,set_type,"
                "weight_kg,reps,duration_seconds,rpe,rir,notes) "
                "VALUES (%s,%s,%s,%s,'normal',%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(workout_id,exercise_order,set_index) DO UPDATE SET "
                "exercise_id=EXCLUDED.exercise_id,set_type='normal',weight_kg=EXCLUDED.weight_kg,"
                "reps=EXCLUDED.reps,duration_seconds=EXCLUDED.duration_seconds,"
                "rpe=EXCLUDED.rpe,rir=EXCLUDED.rir,notes=EXCLUDED.notes",
                (workout_id, exercise_id, order, index, record["weight_kg"], record["reps"],
                 record["duration_seconds"], record["rpe"], record["rir"], record["notes"]),
            )
    for offset, ((name, seconds), notes) in enumerate(cardio_entries.items(), start=len(rows)):
        exercise_id = exercise_id_for(cur, name, aliases.get(name))
        orders.append((offset, 0))
        cur.execute(
            "INSERT INTO sets(workout_id,exercise_id,exercise_order,set_index,set_type,"
            "duration_seconds,notes) VALUES (%s,%s,%s,0,'normal',%s,%s) "
            "ON CONFLICT(workout_id,exercise_order,set_index) DO UPDATE SET "
            "exercise_id=EXCLUDED.exercise_id,duration_seconds=EXCLUDED.duration_seconds,"
            "reps=NULL,weight_kg=NULL,rpe=NULL,rir=NULL,notes=EXCLUDED.notes",
            (workout_id, exercise_id, offset, seconds, notes),
        )
    cur.execute("SELECT exercise_order,set_index FROM sets WHERE workout_id=%s", (workout_id,))
    for order, index in set(cur.fetchall()) - set(orders):
        cur.execute("DELETE FROM sets WHERE workout_id=%s AND exercise_order=%s AND set_index=%s",
                    (workout_id, order, index))
    return len(orders)


def session_notes(rows, include_last=False):
    """Notas gerais da sessão (tempo total, sensação, sono), sem interpretar o texto."""
    all_notes = [row["notes"].strip() for row in rows if row["notes"].strip()]
    selected = [note for note in all_notes if re.search(
        r"tempo\s+total|sensa[cç]|cansa[cç]|\bsono\b|\bgeral\b",
        note, re.IGNORECASE)]
    if include_last and all_notes and all_notes[-1] not in selected:
        # Compatibilidade com relatórios antigos que incluíam a última nota
        # mesmo quando descrevia só uma série.
        selected.append(all_notes[-1])
    return "\n".join(dict.fromkeys(selected))


def rows_for_session(title, rows):
    """Em dias de descanso, persistir somente as atividades de cardio."""
    if title.strip().casefold() != "descanso":
        return rows
    cardio = []
    for row in rows:
        if row["is_cardio"]:
            if row["cardio_seconds"] or parsed_sets(row):
                cardio.append(row)
        elif row["cardio_seconds"]:
            cardio.append({**row, "exercise": row["cardio_name"] or "Cardio",
                           "is_cardio": True, "reps": [], "weight": [],
                           "cardio_name": None})
    return cardio


def match_records(logged, target):
    """Associa séries efetivas por posição; se quantidade divergir, apenas por valores únicos."""
    if len(logged) == len(target):
        return list(zip(logged, target)), 0
    matched, remaining = [], list(target)
    for item in logged:
        candidates = [s for s in remaining if
                      item["reps"] == s[3] and item["duration_seconds"] == s[4]
                      and item["weight_kg"] is not None and s[5] is not None
                      and abs(float(item["weight_kg"]) - float(s[5])) < 0.01]
        if len(candidates) == 1:
            matched.append((item, candidates[0]))
            remaining.remove(candidates[0])
    return matched, len(logged) - len(matched)


def merge_session(cur, workout_id, rows, aliases):
    """Somente preenche RIR/notas ausentes; nunca substitui cargas ou reps do Hevy."""
    cur.execute(
        "SELECT s.id,e.canonical_name,s.exercise_order,s.reps,s.duration_seconds,"
        "s.weight_kg,s.rir,s.notes "
        "FROM sets s JOIN exercises e ON e.id=s.exercise_id "
        "WHERE s.workout_id=%s AND s.set_type <> 'warmup' "
        "ORDER BY s.exercise_order,s.set_index", (workout_id,))
    grouped = defaultdict(lambda: defaultdict(list))
    for s in cur.fetchall():
        grouped[s[1]][s[2]].append(s)

    merged_rir = new_rir = notes_added = unmatched_sets = 0
    unresolved = []
    used = set()
    for row in rows:
        recorded = parsed_sets(row)
        if not recorded:
            continue
        canonical = aliases.get(row["exercise"], "")
        if not canonical or len(grouped.get(canonical, {})) != 1 or canonical in used:
            unmatched_sets += len(recorded)
            unresolved.append(row["exercise"])
            continue
        used.add(canonical)
        target = next(iter(grouped[canonical].values()))
        pairs, missing = match_records(recorded, target)
        unmatched_sets += missing
        if missing:
            unresolved.append(f"{row['exercise']} ({missing} séries sem par)")
        for item, saved in pairs:
            sid, _, _, _, _, _, existing_rir, existing_notes = saved
            incoming_rir = item["rir"]
            if incoming_rir is not None:
                merged_rir += 1
                if existing_rir is None:
                    new_rir += 1
            original_note = item["notes"]
            annotated = f"[Obsidian] {original_note}" if original_note else None
            existing_notes = existing_notes or ""
            append_note = annotated and annotated not in existing_notes
            final_notes = (existing_notes + " | " + annotated).strip(" |") if append_note else existing_notes
            if append_note:
                notes_added += 1
            if (incoming_rir is not None and existing_rir is None) or append_note:
                cur.execute("UPDATE sets SET rir=COALESCE(rir,%s),notes=%s WHERE id=%s",
                            (incoming_rir, final_notes or None, sid))

    note = session_notes(rows)
    previous_auto_note = session_notes(rows, include_last=True)
    if previous_auto_note != note:
        # Corrige somente a descrição exatamente igual à gerada pela versão
        # antiga. Descrições próprias do Hevy continuam preservadas.
        cur.execute("UPDATE workouts SET description=%s WHERE id=%s AND description=%s",
                    (note or None, workout_id, previous_auto_note))
    description_added = False
    if note:
        cur.execute("UPDATE workouts SET description=%s WHERE id=%s "
                    "AND NULLIF(BTRIM(description),'') IS NULL RETURNING id",
                    (note, workout_id))
        description_added = cur.fetchone() is not None
    return merged_rir, new_rir, notes_added, unmatched_sets, description_added, unresolved


def run():
    sessions = logs()
    aliases = obsidian_aliases()
    imported = merged = pending = total_sets = total_rir = new_rir = total_notes = unmatched = descriptions = 0
    cardio_sessions = ignored_rest = 0
    pending_lines = []
    merged_lines = []
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for (day, title), rows in sessions.items():
                    rows = rows_for_session(title, rows)
                    if title.strip().casefold() == "descanso":
                        old_id = uuid5(NAMESPACE_URL, f"obsidian:{day.isoformat()}:{title}")
                        if not rows:
                            cur.execute("DELETE FROM workouts WHERE id=%s AND source='obsidian'", (old_id,))
                            ignored_rest += 1
                            continue
                        # Sessão idempotente: manter o UUID original, remover séries
                        # antigas que não sejam cardio e trocar só o título exibido.
                        total_sets += upsert_session(cur, day, title, rows, aliases,
                                                     display_title="Cardio (Descanso)")
                        cardio_sessions += 1
                        continue
                    cur.execute(
                        "SELECT id,title FROM workouts WHERE source='hevy' AND deleted_at IS NULL "
                        "AND (start_time AT TIME ZONE 'America/Sao_Paulo')::date=%s ORDER BY start_time", (day,),
                    )
                    candidates = cur.fetchall()
                    if candidates:
                        if len(candidates) > 1:
                            same_title = [w for w in candidates if w[1] and w[1].casefold() == title.casefold()]
                            candidates = same_title if len(same_title) == 1 else []
                        if not candidates:
                            pending += 1
                            pending_lines.append(f"- {day} — {title}: múltiplos treinos Hevy; requer identificação manual")
                            continue
                        counts = merge_session(cur, candidates[0][0], rows, aliases)
                        rir, newly, notes, missing, described, names = counts
                        total_rir += rir
                        new_rir += newly
                        total_notes += notes
                        unmatched += missing
                        descriptions += int(described)
                        merged += 1
                        merged_lines.append(f"- {day} — {title}: {rir} séries com RIR, "
                                            f"{missing} séries sem correspondência" +
                                            (f" ({', '.join(names)})" if names else ""))
                        # Elimina eventual duplicata antiga apenas após mesclar no Hevy.
                        old_id = uuid5(NAMESPACE_URL, f"obsidian:{day.isoformat()}:{title}")
                        cur.execute("DELETE FROM workouts WHERE id=%s AND source='obsidian'", (old_id,))
                    else:
                        total_sets += upsert_session(cur, day, title, rows, aliases)
                        imported += 1
    output = ROOT / "reports"
    output.mkdir(exist_ok=True)
    content = ["# Importação do Obsidian", "",
               f"Sessões: {imported} importadas sem Hevy, {merged} mescladas com Hevy, {pending} pendentes.",
               f"Descanso: {cardio_sessions} sessões de cardio, {ignored_rest} sem cardio ignoradas.",
               f"Séries importadas para sessões exclusivas: {total_sets}.",
               f"Séries Hevy com RIR conciliado: {total_rir} (novos RIR nesta execução: {new_rir}).",
               f"Notas de séries incluídas nesta execução: {total_notes}.",
               f"Descrições de sessão preenchidas nesta execução: {descriptions}.",
               f"Séries sem correspondência segura: {unmatched}.",
               "", "## Mescladas com Hevy", ""]
    content.extend(merged_lines or ["Nenhuma."])
    content.extend(["", "## Pendentes de identificação", ""])
    content.extend(pending_lines or ["Nenhuma."])
    (output / "importacao-obsidian.md").write_text("\n".join(content) + "\n", encoding="utf-8")
    print(f"Obsidian: {imported} sessões independentes, {merged} mescladas, "
          f"{total_rir} séries com RIR, {unmatched} séries sem correspondência, {pending} pendentes")


if __name__ == "__main__":
    run()
